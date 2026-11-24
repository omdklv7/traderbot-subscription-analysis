
-- ============================================================
-- 1. BUSINESS OVERVIEW
-- Ежемесячные регистрации, активные подписки, MRR и поступления.
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            TIMESTAMP '2025-01-01',
            TIMESTAMP '2026-09-01',
            INTERVAL '1 month'
        ) AS month_start
),
registrations AS (
    SELECT
        DATE_TRUNC(
            'month', timezone('UTC', registered_at)
        )::date AS month,
        COUNT(*) AS new_users,
        COUNT(*) FILTER (
            WHERE initial_model = 'subscription'
        ) AS new_subscription_users,
        COUNT(*) FILTER (
            WHERE initial_model = 'license'
        ) AS new_license_users
    FROM users
    GROUP BY 1
),
active_subscriptions AS (
    SELECT
        m.month_start::date AS month,
        COUNT(DISTINCT sp.subscription_id)
            AS active_paid_subscriptions
    FROM months m
    LEFT JOIN subscription_periods sp
        ON sp.starts_at <
            timezone(
                'UTC',
                m.month_start + INTERVAL '1 month'
            )
       AND COALESCE(sp.canceled_at, sp.ends_at) >=
            timezone(
                'UTC',
                m.month_start + INTERVAL '1 month'
            )
    GROUP BY m.month_start
),
subscription_receipts AS (
    SELECT
        DATE_TRUNC(
            'month', timezone('UTC', confirmed_at)
        )::date AS month,
        SUM(amount_usd) AS subscription_cash_usd
    FROM payments
    WHERE status = 'confirmed'
      AND confirmed_at <
          '2026-10-01 00:00:00+00'::timestamptz
    GROUP BY 1
),
license_receipts AS (
    SELECT
        DATE_TRUNC(
            'month', timezone('UTC', purchased_at)
        )::date AS month,
        SUM(amount_usd) AS license_cash_usd
    FROM license_purchases
    WHERE purchased_at <
          '2026-10-01 00:00:00+00'::timestamptz
    GROUP BY 1
)

SELECT
    m.month_start::date AS month,

    COALESCE(r.new_users, 0) AS new_users,
    COALESCE(r.new_subscription_users, 0)
        AS new_subscription_users,
    COALESCE(r.new_license_users, 0)
        AS new_license_users,
    a.active_paid_subscriptions,
    a.active_paid_subscriptions * 50.00 AS mrr_usd,
    COALESCE(s.subscription_cash_usd, 0)
        AS subscription_cash_usd,
    COALESCE(l.license_cash_usd, 0)
        AS license_cash_usd,
    COALESCE(s.subscription_cash_usd, 0)
    + COALESCE(l.license_cash_usd, 0)
        AS total_cash_usd
FROM months m
LEFT JOIN registrations r
    ON m.month_start::date = r.month
LEFT JOIN active_subscriptions a
    ON m.month_start::date = a.month
LEFT JOIN subscription_receipts s
    ON m.month_start::date = s.month
LEFT JOIN license_receipts l
    ON m.month_start::date = l.month
ORDER BY month;



-- ============================================================
-- 2. CONVERSION & RETENTION
-- Конверсия, продления, отток и реактивации по месяцам.
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            DATE '2025-01-01',
            DATE '2026-09-01',
            INTERVAL '1 month'
        )::date AS month
),

-- Конверсия за 30 дней по месяцу регистрации
user_conversion AS (
    SELECT
        DATE_TRUNC(
            'month', timezone('UTC', u.registered_at)
        )::date AS month,
        u.initial_model,

        CASE
            WHEN u.initial_model = 'subscription'
             AND EXISTS (
                SELECT 1
                FROM subscriptions s
                JOIN payments p
                    ON s.subscription_id = p.subscription_id
                WHERE s.user_id = u.user_id
                  AND p.status = 'confirmed'
                  AND p.confirmed_at >= u.registered_at
                  AND p.confirmed_at <
                      u.registered_at + INTERVAL '30 days'
            ) THEN 1

            WHEN u.initial_model = 'license'
             AND EXISTS (
                SELECT 1
                FROM license_purchases lp
                WHERE lp.user_id = u.user_id
                  AND lp.purchased_at >= u.registered_at
                  AND lp.purchased_at <
                      u.registered_at + INTERVAL '30 days'
            ) THEN 1

            ELSE 0
        END AS converted

    FROM users u
    WHERE u.registered_at + INTERVAL '30 days'
          <= '2026-10-01 00:00:00+00'::timestamptz
),

conversion_stats AS (
    SELECT
        month,
        COUNT(*) FILTER (
            WHERE initial_model = 'subscription'
        ) AS subscription_users,

        SUM(converted) FILTER (
            WHERE initial_model = 'subscription'
        ) AS subscription_paid_30d,

        COUNT(*) FILTER (
            WHERE initial_model = 'license'
        ) AS license_users,

        SUM(converted) FILTER (
            WHERE initial_model = 'license'
        ) AS license_paid_30d

    FROM user_conversion
    GROUP BY month
),

-- Продления по месяцу окончания оплаченного периода
period_events AS (
    SELECT
        DATE_TRUNC(
            'month', timezone('UTC', sp.ends_at)
        )::date AS month,

        sp.period_no,
        sp.ends_at,
        sp.canceled_at,

        next_sp.period_id AS next_period_id,
        next_sp.starts_at AS next_starts_at,
        p.confirmed_at AS next_payment_at,

        CASE
            WHEN sp.canceled_at IS NULL
             AND next_sp.starts_at = sp.ends_at
             AND p.status = 'confirmed'
             AND p.confirmed_at <= sp.ends_at
                THEN 1
            ELSE 0
        END AS renewed

    FROM subscription_periods sp

    LEFT JOIN subscription_periods next_sp
        ON sp.subscription_id = next_sp.subscription_id
       AND next_sp.period_no = sp.period_no + 1

    LEFT JOIN payments p
        ON next_sp.payment_id = p.payment_id

    WHERE sp.ends_at <=
        '2026-10-01 00:00:00+00'::timestamptz
),

renewal_stats AS (
    SELECT
        month,

        COUNT(*) FILTER (
            WHERE period_no = 1
        ) AS eligible_first_periods,

        COUNT(*) FILTER (
            WHERE period_no = 1 AND renewed = 1
        ) AS first_renewals,

        COUNT(*) AS eligible_periods,
        SUM(renewed) AS renewed_periods,
        COUNT(*) - SUM(renewed) AS churned_periods

    FROM period_events
    GROUP BY month
),

-- Возвраты в течение 30 дней после просрочки
reactivation_stats AS (
    SELECT
        month,

        COUNT(*) AS eligible_expired_periods,

        COUNT(*) FILTER (
            WHERE next_starts_at > ends_at
              AND next_starts_at <=
                  ends_at + INTERVAL '30 days'
              AND next_payment_at > ends_at
              AND next_payment_at <=
                  ends_at + INTERVAL '30 days'
        ) AS reactivated_30d

    FROM period_events

    WHERE canceled_at IS NULL
      AND ends_at + INTERVAL '30 days' <=
          '2026-10-01 00:00:00+00'::timestamptz

      AND (
          next_period_id IS NULL
          OR next_starts_at > ends_at
      )

    GROUP BY month
)

SELECT
    m.month,

    COALESCE(c.subscription_users, 0)
        AS subscription_users,

    COALESCE(c.subscription_paid_30d, 0)
        AS subscription_paid_30d,

    ROUND(
        100.0 * c.subscription_paid_30d
        / NULLIF(c.subscription_users, 0), 2
    ) AS subscription_conversion_30d_pct,

    COALESCE(c.license_users, 0)
        AS license_users,

    COALESCE(c.license_paid_30d, 0)
        AS license_paid_30d,

    ROUND(
        100.0 * c.license_paid_30d
        / NULLIF(c.license_users, 0), 2
    ) AS license_conversion_30d_pct,

    COALESCE(r.eligible_first_periods, 0)
        AS eligible_first_periods,

    COALESCE(r.first_renewals, 0)
        AS first_renewals,

    ROUND(
        100.0 * r.first_renewals
        / NULLIF(r.eligible_first_periods, 0), 2
    ) AS first_renewal_rate_pct,

    COALESCE(r.eligible_periods, 0)
        AS eligible_periods,

    COALESCE(r.renewed_periods, 0)
        AS renewed_periods,

    COALESCE(r.churned_periods, 0)
        AS churned_periods,

    ROUND(
        100.0 * r.renewed_periods
        / NULLIF(r.eligible_periods, 0), 2
    ) AS renewal_rate_pct,

    ROUND(
        100.0 * r.churned_periods
        / NULLIF(r.eligible_periods, 0), 2
    ) AS churn_rate_pct,

    COALESCE(a.eligible_expired_periods, 0)
        AS eligible_expired_periods,

    COALESCE(a.reactivated_30d, 0)
        AS reactivated_30d,

    ROUND(
        100.0 * a.reactivated_30d
        / NULLIF(a.eligible_expired_periods, 0), 2
    ) AS reactivation_rate_30d_pct

FROM months m

LEFT JOIN conversion_stats c
    ON m.month = c.month

LEFT JOIN renewal_stats r
    ON m.month = r.month

LEFT JOIN reactivation_stats a
    ON m.month = a.month

ORDER BY m.month;

