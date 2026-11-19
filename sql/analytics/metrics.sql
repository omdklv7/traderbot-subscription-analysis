-- ============================================================
-- 1. 30-DAY PAYMENT CONVERSION
-- Конверсия регистрации в оплату подписки за 30 дней
-- ============================================================

WITH chislitel_1 AS (
SELECT
	COUNT(DISTINCT u.user_id) AS paid_users_30d
FROM
	users u
JOIN subscriptions s
        ON
	u.user_id = s.user_id
JOIN payments p
        ON
	s.subscription_id = p.subscription_id
WHERE
	u.initial_model = 'subscription'
	AND p.status = 'confirmed'
	AND p.confirmed_at >= u.registered_at
	AND p.confirmed_at < u.registered_at + INTERVAL '30 days'
),
znamenatel_1 AS (
SELECT
	COUNT(*) AS total_users
FROM
	users
WHERE
	initial_model = 'subscription'
)
SELECT
	z.total_users,
	c.paid_users_30d,
	ROUND(
        100.0 * c.paid_users_30d / NULLIF(z.total_users, 0),
        2
    ) AS conversion_30d
FROM
	chislitel_1 c
CROSS JOIN znamenatel_1 z;

-- ============================================================
-- 2. ACTIVATION WITHIN 24 HOURS
-- Доля успешных активаций в течение суток
-- ============================================================

WITH chislitel_2 AS (
SELECT
	COUNT(activation_id) AS activations_24h
FROM
	activations
WHERE
	status = 'completed'
	AND completed_at <= requested_at + INTERVAL '24 hours'
	AND requested_at < '2026-09-30 00:00:00+00'::timestamptz),
znamenatel_2 AS (
SELECT
	COUNT(activation_id) AS total_activations
FROM
	activations
WHERE
	requested_at < '2026-09-30 00:00:00+00'::timestamptz)
SELECT
	c.activations_24h,
	z.total_activations,
	ROUND(100.0 * c.activations_24h / NULLIF(z.total_activations, 0), 2) AS activation_rate_24h
FROM
	chislitel_2 c
CROSS JOIN znamenatel_2 z;

-- ============================================================
-- 3. ACTIVATION TIME
-- Среднее, медиана и P90 времени активации
-- ============================================================

WITH activation_duration AS (
    SELECT
        activation_id,
        EXTRACT(
            EPOCH FROM completed_at - requested_at
        ) / 60.0 AS duration_minutes
    FROM activations
    WHERE status = 'completed'
      AND completed_at < '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    COUNT(*) AS total_activations,
    ROUND(AVG(duration_minutes), 2) AS avg_minutes,
    ROUND(
        PERCENTILE_CONT(0.5)
        WITHIN GROUP (ORDER BY duration_minutes)::numeric,
        2
    ) AS median_minutes,
    ROUND(
        PERCENTILE_CONT(0.9)
        WITHIN GROUP (ORDER BY duration_minutes)::numeric,
        2
    ) AS p90_minutes
FROM activation_duration;

-- ============================================================
-- 4. FIRST RENEWAL RATE
-- Доля первых своевременных продлений подписки
-- ============================================================

WITH renewal_check AS (
    SELECT
        sp.subscription_id,
        sp.period_id,
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
    WHERE sp.period_no = 1
      AND sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    COUNT(*) AS eligible_subscriptions,
    SUM(renewed) AS first_renewals,
    ROUND(
        100.0 * SUM(renewed) / NULLIF(COUNT(*), 0),
        2
    ) AS first_renewal_rate
FROM renewal_check;

-- ============================================================
-- 5. RENEWAL RATE
-- Доля всех своевременно продлённых оплаченных периодов
-- ============================================================

WITH renewal_check AS (
    SELECT
        sp.period_id,
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
    WHERE sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    COUNT(*) AS eligible_periods,
    SUM(renewed) AS renewed_periods,
    ROUND(
        100.0 * SUM(renewed) / NULLIF(COUNT(*), 0),
        2
    ) AS renewal_rate
FROM renewal_check;

-- ============================================================
-- 6. CHURN RATE
-- Доля оплаченных периодов без своевременного продления
-- ============================================================

WITH renewal_check AS (
    SELECT
        sp.period_id,
        CASE
            WHEN sp.canceled_at IS NULL
             AND next_sp.starts_at = sp.ends_at
             AND p.status = 'confirmed'
             AND p.confirmed_at <= sp.ends_at
            THEN 0
            ELSE 1
        END AS churned
    FROM subscription_periods sp
    LEFT JOIN subscription_periods next_sp
        ON sp.subscription_id = next_sp.subscription_id
       AND next_sp.period_no = sp.period_no + 1
    LEFT JOIN payments p
        ON next_sp.payment_id = p.payment_id
    WHERE sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    COUNT(*) AS eligible_periods,
    SUM(churned) AS churned_periods,
    ROUND(
        100.0 * SUM(churned) / NULLIF(COUNT(*), 0),
        2
    ) AS churn_rate
FROM renewal_check;

-- ============================================================
-- 7. REACTIVATION WITHIN 30 DAYS
-- Доля возвратов в течение 30 дней после просрочки
-- ============================================================

WITH expired_periods AS (
    SELECT
        sp.subscription_id,
        sp.period_id,
        sp.ends_at,
        next_sp.starts_at AS next_start,
        p.confirmed_at AS next_payment_at
    FROM subscription_periods sp
    LEFT JOIN subscription_periods next_sp
        ON sp.subscription_id = next_sp.subscription_id
       AND next_sp.period_no = sp.period_no + 1
    LEFT JOIN payments p
        ON next_sp.payment_id = p.payment_id
    WHERE sp.canceled_at IS NULL
      AND sp.ends_at + INTERVAL '30 days'
          <= '2026-10-01 00:00:00+00'::timestamptz
      AND (
          next_sp.period_id IS NULL
          OR next_sp.starts_at > sp.ends_at
      )
),
reactivation_check AS (
    SELECT
        *,
        CASE
            WHEN next_start > ends_at
             AND next_start <= ends_at + INTERVAL '30 days'
             AND next_payment_at > ends_at
             AND next_payment_at <= ends_at + INTERVAL '30 days'
            THEN 1
            ELSE 0
        END AS reactivated_30d
    FROM expired_periods
)
SELECT
    COUNT(*) AS expired_periods,
    SUM(reactivated_30d) AS reactivated_30d,
    ROUND(
        100.0 * SUM(reactivated_30d)
        / NULLIF(COUNT(*), 0),
        2
    ) AS reactivation_rate_30d
FROM reactivation_check;

-- ============================================================
-- 8. ACTIVE PAID SUBSCRIPTIONS (MONTH-END)
-- Число активных платящих подписок на конец каждого месяца
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            TIMESTAMP '2025-01-01',
            TIMESTAMP '2026-09-01',
            INTERVAL '1 month'
        ) AS month_start
)
SELECT
    TO_CHAR(m.month_start, 'YYYY-MM') AS month,
    COUNT(DISTINCT sp.subscription_id)
        AS active_paid_subscriptions
FROM months m
LEFT JOIN subscription_periods sp
    ON sp.starts_at < (
        (m.month_start + INTERVAL '1 month')
        AT TIME ZONE 'UTC'
    )
    AND COALESCE(sp.canceled_at, sp.ends_at) >= (
        (m.month_start + INTERVAL '1 month')
        AT TIME ZONE 'UTC'
    )
GROUP BY m.month_start
ORDER BY m.month_start;

-- ============================================================
-- 9. MONTHLY RECURRING REVENUE (MRR)
-- Ежемесячная регулярная денежная база
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            TIMESTAMP '2025-01-01',
            TIMESTAMP '2026-09-01',
            INTERVAL '1 month'
        ) AS month_start
),
active_subscriptions AS (
    SELECT
        m.month_start,
        COUNT(DISTINCT sp.subscription_id) AS active_count
    FROM months m
    LEFT JOIN subscription_periods sp
        ON sp.starts_at < (
            (m.month_start + INTERVAL '1 month')
            AT TIME ZONE 'UTC'
        )
       AND COALESCE(sp.canceled_at, sp.ends_at) >= (
            (m.month_start + INTERVAL '1 month')
            AT TIME ZONE 'UTC'
        )
    GROUP BY m.month_start
)
SELECT
    TO_CHAR(month_start, 'YYYY-MM') AS month,
    active_count AS active_paid_subscriptions,
    active_count * 50.00 AS mrr_usd
FROM active_subscriptions
ORDER BY month_start;

-- ============================================================
-- 10. CONFIRMED CASH RECEIPTS
-- Подтверждённые поступления от подписок и лицензий
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            TIMESTAMP '2025-01-01',
            TIMESTAMP '2026-09-01',
            INTERVAL '1 month'
        ) AS month_start
),
subscription_revenue AS (
    SELECT
        DATE_TRUNC(
            'month',
            timezone('UTC', confirmed_at)
        ) AS month_start,
        SUM(amount_usd) AS subscription_usd
    FROM payments
    WHERE status = 'confirmed'
      AND confirmed_at <
          '2026-10-01 00:00:00+00'::timestamptz
    GROUP BY 1
),
license_revenue AS (
    SELECT
        DATE_TRUNC(
            'month',
            timezone('UTC', purchased_at)
        ) AS month_start,
        SUM(amount_usd) AS license_usd
    FROM license_purchases
    WHERE purchased_at <
          '2026-10-01 00:00:00+00'::timestamptz
    GROUP BY 1
)
SELECT
    TO_CHAR(m.month_start, 'YYYY-MM') AS month,

    COALESCE(s.subscription_usd, 0)
        AS subscription_usd,

    COALESCE(l.license_usd, 0)
        AS license_usd,

    COALESCE(s.subscription_usd, 0)
        + COALESCE(l.license_usd, 0)
        AS total_usd
FROM months m
LEFT JOIN subscription_revenue s
    ON m.month_start = s.month_start
LEFT JOIN license_revenue l
    ON m.month_start = l.month_start
ORDER BY m.month_start;

-- ============================================================
-- 11. TECHNICAL INCIDENT IMPACT RATE
-- Воздействие технических инцидентов по месяцам
-- ============================================================

WITH months AS (
    SELECT
        generate_series(
            TIMESTAMP '2025-01-01',
            TIMESTAMP '2026-09-01',
            INTERVAL '1 month'
        ) AS month_start
),
active_subscriptions AS (
    SELECT
        m.month_start,
        COUNT(DISTINCT sp.subscription_id) AS active_count
    FROM months m
    LEFT JOIN subscription_periods sp
        ON sp.starts_at < (
            (m.month_start + INTERVAL '1 month')
            AT TIME ZONE 'UTC'
        )
       AND COALESCE(sp.canceled_at, sp.ends_at) >= (
            (m.month_start + INTERVAL '1 month')
            AT TIME ZONE 'UTC'
        )
    GROUP BY m.month_start
),
impact_stats AS (
    SELECT
        m.month_start,
        i.category,
        COUNT(DISTINCT ii.subscription_id)
            AS affected_subscriptions,
        COUNT(*) AS impact_events
    FROM months m
    JOIN incident_impacts ii
        ON ii.affected_at < (
            (m.month_start + INTERVAL '1 month')
            AT TIME ZONE 'UTC'
        )
       AND COALESCE(
            ii.restored_at,
            '2026-10-01 00:00:00+00'::timestamptz
        ) > (
            m.month_start AT TIME ZONE 'UTC'
        )
    JOIN incidents i
        ON ii.incident_id = i.incident_id
    GROUP BY m.month_start, i.category
),
categories AS (
    SELECT DISTINCT
        category
    FROM incidents
)
SELECT
    TO_CHAR(m.month_start, 'YYYY-MM') AS month,
    c.category,
    a.active_count AS active_paid_subscriptions,
    COALESCE(i.affected_subscriptions, 0)
        AS affected_subscriptions,
    COALESCE(i.impact_events, 0)
        AS impact_events,
    ROUND(
        100.0 * COALESCE(i.impact_events, 0)
        / NULLIF(a.active_count, 0),
        2
    ) AS impacts_per_100_active
FROM months m
CROSS JOIN categories c
JOIN active_subscriptions a
    ON m.month_start = a.month_start
LEFT JOIN impact_stats i
    ON m.month_start = i.month_start
   AND c.category = i.category
ORDER BY m.month_start, c.category;

-- ============================================================
-- 12. INCIDENT RECOVERY TIME (AVG / MEDIAN / P90)
-- Время восстановления после воздействия инцидента
-- ============================================================

WITH recovery_duration AS (
    SELECT
        ii.impact_id,
        DATE_TRUNC(
            'month',	
            i.started_at AT TIME ZONE 'UTC'
        ) AS month_start,
        EXTRACT(
            EPOCH FROM ii.restored_at - ii.affected_at
        ) / 60.0 AS recovery_minutes
    FROM incident_impacts ii
    JOIN incidents i
        ON ii.incident_id = i.incident_id
    WHERE ii.restored_at IS NOT NULL
      AND ii.restored_at <
          '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    TO_CHAR(month_start, 'YYYY-MM') AS month,
    COUNT(*) AS total_recovered_impacts,
    ROUND(
        AVG(recovery_minutes),
        2
    ) AS avg_recovery_minutes,
    ROUND(
        PERCENTILE_CONT(0.5)
        WITHIN GROUP (ORDER BY recovery_minutes)::numeric,
        2
    ) AS median_recovery_minutes,
    ROUND(
        PERCENTILE_CONT(0.9)
        WITHIN GROUP (ORDER BY recovery_minutes)::numeric,
        2
    ) AS p90_recovery_minutes
FROM recovery_duration
GROUP BY month_start
ORDER BY month_start;
