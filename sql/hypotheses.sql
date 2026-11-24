
-- ============================================================
-- 1. ACTIVATION TIME AND FIRST RENEWAL
-- Сравнение первого продления по длительности активации.
-- ============================================================

WITH first_cohort AS (
    SELECT
        sp.subscription_id,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM subscription_periods next_sp
                JOIN payments p
                    ON p.payment_id = next_sp.payment_id
                WHERE next_sp.subscription_id = sp.subscription_id
                  AND next_sp.period_no = 2
                  AND next_sp.starts_at = sp.ends_at
                  AND p.status = 'confirmed'
                  AND p.confirmed_at <= sp.ends_at
            ) THEN 1
            ELSE 0
        END AS renewed
    FROM subscription_periods sp
    WHERE sp.period_no = 1
      AND sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
),
activation_groups AS (
    SELECT
        f.subscription_id,
        f.renewed,
        CASE
            WHEN EXTRACT(EPOCH FROM a.completed_at - a.requested_at) / 60.0 <= 30
                THEN 1
            WHEN EXTRACT(EPOCH FROM a.completed_at - a.requested_at) / 60.0 <= 240
                THEN 2
            ELSE 3
        END AS group_id
    FROM first_cohort f
    JOIN activations a
        ON f.subscription_id = a.subscription_id
    WHERE a.status = 'completed'
)
SELECT
    CASE group_id
        WHEN 1 THEN '15-30 min'
        WHEN 2 THEN '31-240 min'
        ELSE '>240 min'
    END AS activation_group,
    COUNT(*) AS total_subscriptions,
    SUM(renewed) AS renewed_subscriptions,
    ROUND(
        100.0 * SUM(renewed) / NULLIF(COUNT(*), 0),
        2
    ) AS first_renewal_rate
FROM activation_groups
GROUP BY group_id
ORDER BY group_id;


-- ============================================================
-- 2. INCIDENTS AND FIRST RENEWAL
-- Сравнение первого продления у затронутых и незатронутых.
-- ============================================================

WITH first_cohort AS (
    SELECT
        sp.subscription_id,
        sp.starts_at,
        sp.ends_at,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM subscription_periods next_sp
                JOIN payments p
                    ON p.payment_id = next_sp.payment_id
                WHERE next_sp.subscription_id = sp.subscription_id
                  AND next_sp.period_no = 2
                  AND next_sp.starts_at = sp.ends_at
                  AND p.status = 'confirmed'
                  AND p.confirmed_at <= sp.ends_at
            ) THEN 1
            ELSE 0
        END AS renewed
    FROM subscription_periods sp
    JOIN activations a
        ON sp.subscription_id = a.subscription_id
    WHERE sp.period_no = 1
      AND a.status = 'completed'
      AND sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
),
incident_groups AS (
    SELECT
        f.subscription_id,
        f.renewed,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM incident_impacts ii
                WHERE ii.subscription_id = f.subscription_id
                  AND ii.affected_at >= f.starts_at
                  AND ii.affected_at < f.ends_at - INTERVAL '74 hours'
            ) THEN 1
            ELSE 0
        END AS had_incident
    FROM first_cohort f
)
SELECT
    CASE had_incident
        WHEN 1 THEN 'With incident'
        ELSE 'Without incident'
    END AS incident_group,
    COUNT(*) AS total_subscriptions,
    SUM(renewed) AS renewed_subscriptions,
    ROUND(
        100.0 * SUM(renewed) / NULLIF(COUNT(*), 0),
        2
    ) AS first_renewal_rate
FROM incident_groups
GROUP BY had_incident
ORDER BY had_incident DESC;


-- ============================================================
-- 3. SUBSCRIPTION VS LICENSE CONVERSION
-- Сравнение конверсии в оплату за первые 30 дней.
-- ============================================================

WITH user_conversion AS (
    SELECT
        u.user_id,
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
                  AND p.confirmed_at < u.registered_at + INTERVAL '30 days'
             ) THEN 1

            WHEN u.initial_model = 'license'
             AND EXISTS (
                SELECT 1
                FROM license_purchases lp
                WHERE lp.user_id = u.user_id
                  AND lp.purchased_at >= u.registered_at
                  AND lp.purchased_at < u.registered_at + INTERVAL '30 days'
             ) THEN 1

            ELSE 0
        END AS converted
    FROM users u
    WHERE u.registered_at + INTERVAL '30 days'
          <= '2026-10-01 00:00:00+00'::timestamptz
)
SELECT
    initial_model,
    COUNT(*) AS total_users,
    SUM(converted) AS paid_users_30d,
    ROUND(
        100.0 * SUM(converted) / NULLIF(COUNT(*), 0),
        2
    ) AS conversion_30d
FROM user_conversion
GROUP BY initial_model
ORDER BY initial_model;


-- ============================================================
-- 4. SETTINGS CHANGES AND FIRST RENEWAL
-- Сравнение первого продления по изменению настроек.
-- ============================================================

WITH first_cohort AS (
    SELECT
        sp.subscription_id,
        sp.starts_at,
        sp.ends_at,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM subscription_periods next_sp
                JOIN payments p
                    ON p.payment_id = next_sp.payment_id
                WHERE next_sp.subscription_id = sp.subscription_id
                  AND next_sp.period_no = 2
                  AND next_sp.starts_at = sp.ends_at
                  AND p.status = 'confirmed'
                  AND p.confirmed_at <= sp.ends_at
            ) THEN 1
            ELSE 0
        END AS renewed
    FROM subscription_periods sp
    JOIN activations a
        ON sp.subscription_id = a.subscription_id
    WHERE sp.period_no = 1
      AND a.status = 'completed'
      AND sp.ends_at <= '2026-10-01 00:00:00+00'::timestamptz
),
settings_groups AS (
    SELECT
        f.subscription_id,
        f.renewed,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM setting_changes sc
                WHERE sc.subscription_id = f.subscription_id
                  AND sc.changed_at >= f.starts_at
                  AND sc.changed_at < f.ends_at - INTERVAL '74 hours'
            ) THEN 1
            ELSE 0
        END AS changed_settings
    FROM first_cohort f
)
SELECT
    CASE changed_settings
        WHEN 1 THEN 'Changed settings'
        ELSE 'No settings changes'
    END AS settings_group,
    COUNT(*) AS total_subscriptions,
    SUM(renewed) AS renewed_subscriptions,
    ROUND(
        100.0 * SUM(renewed) / NULLIF(COUNT(*), 0),
        2
    ) AS first_renewal_rate
FROM settings_groups
GROUP BY changed_settings
ORDER BY changed_settings DESC;
