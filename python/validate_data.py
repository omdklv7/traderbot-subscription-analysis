import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"

# Таблицы и их первичные ключи
PRIMARY_KEYS = {
    "users": "user_id",
    "subscriptions": "subscription_id",
    "payments": "payment_id",
    "subscription_periods": "period_id",
    "activations": "activation_id",
    "setting_changes": "change_id",
    "incidents": "incident_id",
    "incident_impacts": "impact_id",
    "support_tickets": "ticket_id",
    "license_purchases": "license_purchase_id",
}

# Связи между таблицами
FOREIGN_KEYS = [
    ("subscriptions", "user_id", "users", "user_id"),
    ("payments", "subscription_id", "subscriptions", "subscription_id"),
    ("subscription_periods", "subscription_id", "subscriptions", "subscription_id"),
    ("subscription_periods", "payment_id", "payments", "payment_id"),
    ("activations", "subscription_id", "subscriptions", "subscription_id"),
    ("setting_changes", "subscription_id", "subscriptions", "subscription_id"),
    ("incident_impacts", "incident_id", "incidents", "incident_id"),
    ("incident_impacts", "subscription_id", "subscriptions", "subscription_id"),
    ("support_tickets", "subscription_id", "subscriptions", "subscription_id"),
    ("license_purchases", "user_id", "users", "user_id"),
]


def load_tables():
    data = {}

    for table in PRIMARY_KEYS:
        path = DATA_DIR / f"{table}.csv"

        with path.open(
            "r", encoding="utf-8", newline=""
        ) as file:
            data[table] = list(csv.DictReader(file))

        print(f"{table}: {len(data[table])} строк")

    return data


def validate_primary_keys(data):
    for table, pk in PRIMARY_KEYS.items():
        values = [row[pk] for row in data[table]]

        assert all(values), f"Пустой PK в {table}"
        assert len(values) == len(set(values)), (
            f"Повторяющиеся PK в {table}"
        )

    print("Первичные ключи: OK")


def validate_foreign_keys(data):
    for child, child_col, parent, parent_col in FOREIGN_KEYS:
        valid_ids = {
            row[parent_col] for row in data[parent]
        }

        assert all(
            row[child_col] in valid_ids
            for row in data[child]
        ), f"Нарушена связь {child}.{child_col} → {parent}"

    print("Внешние ключи: OK")


def validate_business_constraints(data):
    # Одна подписка на пользователя
    user_ids = [
        s["user_id"] for s in data["subscriptions"]
    ]
    assert len(user_ids) == len(set(user_ids))

    # Уникальность номера периода внутри подписки
    period_keys = [
        (p["subscription_id"], p["period_no"])
        for p in data["subscription_periods"]
    ]
    assert len(period_keys) == len(set(period_keys))

    # Каждый оплаченный период связан со своим платежом
    payments = {
        p["payment_id"]: p for p in data["payments"]
    }

    for period in data["subscription_periods"]:
        payment = payments[period["payment_id"]]

        assert payment["status"] == "confirmed"
        assert payment["subscription_id"] == period["subscription_id"]

    print("Связи платежей и периодов: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Проверяем даты и пересечения оплаченных периодов
def validate_subscription_timeline(data):
    observation_end = datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )

    payments = {
        p["payment_id"]: p
        for p in data["payments"]
    }

    periods_by_sub = {}

    for period in data["subscription_periods"]:
        subscription_id = period["subscription_id"]

        start = datetime.fromisoformat(period["starts_at"])
        end = datetime.fromisoformat(period["ends_at"])

        payment = payments[period["payment_id"]]

        initiated = datetime.fromisoformat(
            payment["initiated_at"]
        )

        confirmed = datetime.fromisoformat(
            payment["confirmed_at"]
        )

        # Проверка дат оплаты и оплаченного периода
        assert initiated <= confirmed < observation_end
        assert confirmed <= start < end

        # Проверка досрочной отмены
        if period["canceled_at"]:
            canceled = datetime.fromisoformat(
                period["canceled_at"]
            )
            assert start <= canceled < end

        periods_by_sub.setdefault(
            subscription_id, []
        ).append(period)

    # Проверяем историю каждой подписки
    for subscription_id, periods in periods_by_sub.items():

        periods.sort(key=lambda p: int(p["period_no"]))

        for index, period in enumerate(periods):
            # Номера периодов идут последовательно
            assert int(period["period_no"]) == index + 1

            if index == 0:
                continue

            previous = periods[index - 1]

            previous_end = datetime.fromisoformat(
                previous["ends_at"]
            )

            current_start = datetime.fromisoformat(
                period["starts_at"]
            )

            # Пересечения запрещены, перерывы разрешены
            assert current_start >= previous_end, (
                f"Пересечение периодов: {subscription_id}"
            )

    print("Хронология оплаченных периодов: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Проверяем регистрации, платежи и активации
def validate_user_events(data):
    observation_end = datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )

    users = {
        u["user_id"]: u
        for u in data["users"]
    }

    subscriptions = {
        s["subscription_id"]: s
        for s in data["subscriptions"]
    }

    payments = {
        p["payment_id"]: p
        for p in data["payments"]
    }

    # 1. Проверяем даты создания подписок
    for subscription in subscriptions.values():
        user = users[subscription["user_id"]]

        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        created_at = datetime.fromisoformat(
            subscription["created_at"]
        )

        assert registered_at <= created_at < observation_end

    print("Регистрации и создание подписок: OK")

    # 2. Проверяем хронологию платежей
    for payment in payments.values():
        subscription = subscriptions[
            payment["subscription_id"]
        ]

        created_at = datetime.fromisoformat(
            subscription["created_at"]
        )

        initiated_at = datetime.fromisoformat(
            payment["initiated_at"]
        )

        assert created_at <= initiated_at < observation_end

        if payment["status"] == "confirmed":
            confirmed_at = datetime.fromisoformat(
                payment["confirmed_at"]
            )

            assert initiated_at <= confirmed_at < observation_end

        else:
            assert payment["confirmed_at"] == ""

    print("Хронология платежей: OK")

    # 3. Находим первую успешную оплату подписки
    first_payments = {}

    for period in data["subscription_periods"]:
        if int(period["period_no"]) == 1:
            first_payments[period["subscription_id"]] = (
                payments[period["payment_id"]]
            )

    # 4. Проверяем активации
    for activation in data["activations"]:
        subscription_id = activation["subscription_id"]

        payment = first_payments[subscription_id]

        confirmed_at = datetime.fromisoformat(
            payment["confirmed_at"]
        )

        requested_at = datetime.fromisoformat(
            activation["requested_at"]
        )

        assert confirmed_at <= requested_at < observation_end

        if activation["status"] == "completed":
            completed_at = datetime.fromisoformat(
                activation["completed_at"]
            )

            assert requested_at <= completed_at < observation_end

        else:
            assert activation["completed_at"] == ""

    print("Хронология активаций: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Проверка setting_changes, incidents и incident_impacts
def validate_activity_events(data):
    observation_end = datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )

    # Подготавливаем справочники
    activations = {
        a["subscription_id"]: a
        for a in data["activations"]
    }

    incidents = {
        i["incident_id"]: i
        for i in data["incidents"]
    }

    periods_by_sub = {}

    for period in data["subscription_periods"]:
        periods_by_sub.setdefault(
            period["subscription_id"], []
        ).append(period)

    # 1. Проверяем изменения настроек
    changes_by_sub = {}

    for change in data["setting_changes"]:
        subscription_id = change["subscription_id"]
        activation = activations[subscription_id]

        assert activation["status"] == "completed"

        completed_at = datetime.fromisoformat(
            activation["completed_at"]
        )

        changed_at = datetime.fromisoformat(
            change["changed_at"]
        )

        assert completed_at <= changed_at < observation_end

        # Изменение должно происходить в оплаченном периоде
        assert any(
            datetime.fromisoformat(p["starts_at"])
            <= changed_at
            < datetime.fromisoformat(p["ends_at"])
            for p in periods_by_sub[subscription_id]
        )

        changes_by_sub.setdefault(
            subscription_id, []
        ).append(change)

    # Проверяем, что настройки действительно менялись
    for changes in changes_by_sub.values():
        changes.sort(key=lambda c: c["changed_at"])

        previous = ("medium", "balanced")

        for change in changes:
            current = (
                change["risk_level"],
                change["trading_mode"]
            )

            assert current != previous
            previous = current

    print("Изменения настроек: OK")

    # 2. Проверяем технические инциденты
    for incident in incidents.values():
        started_at = datetime.fromisoformat(
            incident["started_at"]
        )

        resolved_at = datetime.fromisoformat(
            incident["resolved_at"]
        )

        assert started_at < resolved_at < observation_end

        assert incident["severity"] in {
            "low", "medium", "high", "critical"
        }

    print("Технические инциденты: OK")

    # 3. Проверяем воздействия на подписчиков
    for impact in data["incident_impacts"]:
        subscription_id = impact["subscription_id"]
        incident = incidents[impact["incident_id"]]
        activation = activations[subscription_id]

        assert activation["status"] == "completed"

        activated_at = datetime.fromisoformat(
            activation["completed_at"]
        )

        affected_at = datetime.fromisoformat(
            impact["affected_at"]
        )

        restored_at = datetime.fromisoformat(
            impact["restored_at"]
        )

        incident_start = datetime.fromisoformat(
            incident["started_at"]
        )

        incident_end = datetime.fromisoformat(
            incident["resolved_at"]
        )

        # Воздействие только во время инцидента
        assert incident_start <= affected_at < incident_end
        assert restored_at == incident_end

        # Воздействие только после активации
        assert activated_at <= affected_at

        # В момент воздействия есть оплаченный доступ
        assert any(
            datetime.fromisoformat(p["starts_at"])
            <= affected_at
            < datetime.fromisoformat(p["ends_at"])
            for p in periods_by_sub[subscription_id]
        )

    print("Воздействия инцидентов: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Проверка обращений в поддержку и покупок лицензий
def validate_support_and_licenses(data):
    observation_end = datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )

    users = {
        u["user_id"]: u
        for u in data["users"]
    }

    subscriptions = {
        s["subscription_id"]: s
        for s in data["subscriptions"]
    }

    activations = {
        a["subscription_id"]: a
        for a in data["activations"]
    }

    # Группируем неуспешные платежи
    failed_payments = {}

    for payment in data["payments"]:
        if payment["status"] == "failed":
            failed_payments.setdefault(
                payment["subscription_id"], []
            ).append(payment)

    # Группируем воздействия инцидентов
    impacts_by_sub = {}

    for impact in data["incident_impacts"]:
        impacts_by_sub.setdefault(
            impact["subscription_id"], []
        ).append(impact)

    # Группируем оплаченные периоды
    periods_by_sub = {}

    for period in data["subscription_periods"]:
        periods_by_sub.setdefault(
            period["subscription_id"], []
        ).append(period)

    # 1. Проверяем обращения в поддержку
    for ticket in data["support_tickets"]:
        subscription_id = ticket["subscription_id"]

        opened_at = datetime.fromisoformat(
            ticket["opened_at"]
        )

        subscription = subscriptions[subscription_id]

        created_at = datetime.fromisoformat(
            subscription["created_at"]
        )

        assert created_at <= opened_at < observation_end

        # Дата закрытия
        if ticket["closed_at"]:
            closed_at = datetime.fromisoformat(
                ticket["closed_at"]
            )

            assert opened_at <= closed_at < observation_end

        category = ticket["category"]

        assert category in {
            "activation", "payment", "technical", "general"
        }

        # Обращение по активации
        if category == "activation":
            activation = activations[subscription_id]

            requested_at = datetime.fromisoformat(
                activation["requested_at"]
            )

            assert requested_at <= opened_at

        # Обращение по оплате
        elif category == "payment":
            assert any(
                datetime.fromisoformat(p["initiated_at"])
                <= opened_at
                <= datetime.fromisoformat(
                    p["initiated_at"]
                ) + timedelta(hours=2)
                for p in failed_payments.get(
                    subscription_id, []
                )
            ), "Обращение по оплате без неуспешного платежа"

        # Обращение из-за технического инцидента
        elif category == "technical":
            assert any(
                datetime.fromisoformat(i["affected_at"])
                <= opened_at
                < datetime.fromisoformat(i["restored_at"])
                for i in impacts_by_sub.get(
                    subscription_id, []
                )
            ), "Техническое обращение без воздействия инцидента"

        # Общее обращение
        elif category == "general":
            activation = activations[subscription_id]

            assert activation["status"] == "completed"

            assert opened_at >= datetime.fromisoformat(
                activation["completed_at"]
            )

            assert any(
                datetime.fromisoformat(p["starts_at"])
                <= opened_at
                < datetime.fromisoformat(p["ends_at"])
                for p in periods_by_sub[subscription_id]
            )

    print("Обращения в поддержку: OK")

    # 2. Проверяем покупки лицензий
    purchased_users = set()

    for purchase in data["license_purchases"]:
        user_id = purchase["user_id"]
        user = users[user_id]

        assert user_id not in purchased_users
        purchased_users.add(user_id)

        assert user["initial_model"] == "license"

        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        purchased_at = datetime.fromisoformat(
            purchase["purchased_at"]
        )

        # Покупка после регистрации,
        # не позднее 90 дней
        assert (
            registered_at <= purchased_at
            <= registered_at + timedelta(days=90)
        )

        assert purchased_at < observation_end

        # Проверяем стоимость лицензии
        assert Decimal(purchase["amount_usd"]) == Decimal("550.00")

    print("Покупки лицензий: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Финальный аудит ограничений UNIQUE
def validate_unique_constraints(data):
    unique_fields = [
        ("subscriptions", "user_id"),
        ("activations", "subscription_id"),
        ("subscription_periods", "payment_id")
    ]

    for table, field in unique_fields:
        values = [row[field] for row in data[table]]

        assert len(values) == len(set(values)), (
            f"Нарушена уникальность {table}.{field}"
        )

    # Один инцидент не должен дважды
    # затрагивать одну и ту же подписку
    impact_pairs = [
        (i["incident_id"], i["subscription_id"])
        for i in data["incident_impacts"]
    ]

    assert len(impact_pairs) == len(set(impact_pairs)), (
        "Повторяющиеся воздействия инцидентов"
    )

    # Каждый подтверждённый платёж
    # должен соответствовать оплаченному периоду
    confirmed_ids = {
        p["payment_id"]
        for p in data["payments"]
        if p["status"] == "confirmed"
    }

    period_payment_ids = {
        p["payment_id"]
        for p in data["subscription_periods"]
    }

    assert confirmed_ids == period_payment_ids, (
        "Несоответствие подтверждённых платежей "
        "и оплаченных периодов"
    )

    print("Дополнительные ограничения UNIQUE: OK")
    print("Полнота подтверждённых платежей: OK")

# ---------------------------------------------------------------------------------------------------------------------

# Проверка аналитических метрик
def validate_analytics_windows(data):
    observation_end = datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )

    users = {
        u["user_id"]: u
        for u in data["users"]
    }

    subscriptions = {
        s["subscription_id"]: s
        for s in data["subscriptions"]
    }

    payments = {
        p["payment_id"]: p
        for p in data["payments"]
    }

    # 1. Проверяем полноту 30-дневного наблюдения
    eligible_users = {
        user_id
        for user_id, user in users.items()
        if datetime.fromisoformat(
            user["registered_at"]
        ) + timedelta(days=30) <= observation_end
    }

    assert len(eligible_users) == len(users), (
        "Не все пользователи наблюдались 30 дней"
    )

    print("30-дневное окно наблюдения: OK")

    # 2. Получаем первые и вторые оплаченные периоды
    first_periods = {
        p["subscription_id"]: p
        for p in data["subscription_periods"]
        if int(p["period_no"]) == 1
    }

    second_periods = {
        p["subscription_id"]: p
        for p in data["subscription_periods"]
        if int(p["period_no"]) == 2
    }

    # 3. Проверяем First Renewal Rate
    eligible_first = 0
    first_renewed = 0

    for subscription_id, first in first_periods.items():
        first_end = datetime.fromisoformat(
            first["ends_at"]
        )

        if first_end > observation_end:
            continue

        eligible_first += 1

        second = second_periods.get(subscription_id)

        if second is not None:
            second_start = datetime.fromisoformat(
                second["starts_at"]
            )

            # Только непрерывное продление
            if second_start == first_end:
                first_renewed += 1

    print("Подписок для оценки:", eligible_first)
    print("Первых продлений:", first_renewed)
    print(
        "First Renewal Rate:",
        f"{first_renewed / eligible_first:.2%}"
        if eligible_first else "N/A"
    )

    # 4. Конверсия подписочной модели за 30 дней
    subscription_paid_30 = 0

    for subscription_id, first in first_periods.items():
        user_id = subscriptions[subscription_id]["user_id"]

        registered_at = datetime.fromisoformat(
            users[user_id]["registered_at"]
        )

        payment = payments[first["payment_id"]]

        confirmed_at = datetime.fromisoformat(
            payment["confirmed_at"]
        )

        if confirmed_at < registered_at + timedelta(days=30):
            subscription_paid_30 += 1

    subscription_users = sum(
        u["initial_model"] == "subscription"
        for u in users.values()
    )

    # 5. Конверсия лицензионной модели за 30 дней
    license_paid_30 = 0

    for purchase in data["license_purchases"]:
        user = users[purchase["user_id"]]

        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        purchased_at = datetime.fromisoformat(
            purchase["purchased_at"]
        )

        if purchased_at < registered_at + timedelta(days=30):
            license_paid_30 += 1

    license_users = sum(
        u["initial_model"] == "license"
        for u in users.values()
    )

    print("\nКонверсия в оплату за 30 дней:")

    print(
        "Подписка:",
        f"{subscription_paid_30 / subscription_users:.2%}"
    )

    print(
        "Лицензия:",
        f"{license_paid_30 / license_users:.2%}"
    )

    print("\nАналитические окна проверены")

# ---------------------------------------------------------------------------------------------------------------------

# Итоги проверок
if __name__ == "__main__":
    print("=== DATA QUALITY CHECK ===")

    data = load_tables()

    validate_primary_keys(data)
    validate_foreign_keys(data)
    validate_business_constraints(data)
    validate_subscription_timeline(data)
    validate_user_events(data)
    validate_activity_events(data)
    validate_support_and_licenses(data)
    validate_unique_constraints(data)
    validate_analytics_windows(data)

    print("\nВсе проверки Data Quality пройдены")
