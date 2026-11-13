from collections import Counter
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from calendar import monthrange

# Параметры генерации
SEED = 42
N_USERS = 10_000

REGISTRATION_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
REGISTRATION_END = datetime(2026, 7, 1, tzinfo=timezone.utc)
OBSERVATION_END = datetime(2026, 10, 1, tzinfo=timezone.utc)

# Путь для сохранения данных
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"

# Учет календарны месяцев 
def add_one_month(dt):
    year = dt.year + (dt.month == 12)
    month = dt.month % 12 + 1

    day = min(
        dt.day,
        monthrange(year, month)[1]
    )

    return dt.replace(
        year=year,
        month=month,
        day=day
    )

# ---------------------------------------------------------------------------------------------------------------------

def generate_users():
    rng = random.Random(SEED)
    users = []

    total_seconds = int(
        (REGISTRATION_END - REGISTRATION_START).total_seconds()
    )

    for user_id in range(1, N_USERS + 1):
        # Случайная дата регистрации
        offset = rng.randrange(total_seconds)
        registered_at = REGISTRATION_START + timedelta(seconds=offset)

        # Выбор модели покупки
        initial_model = rng.choices(
            ["subscription", "license"],
            weights=[70, 30]
        )[0]

        # Канал привлечения
        signup_source = rng.choices(
            ["website", "telegram", "referral", "ads"],
            weights=[50, 25, 15, 10]
        )[0]

        # Способ авторизации
        auth_method = rng.choice(["email", "telegram"])

        users.append({
            "user_id": user_id,
            "registered_at": registered_at.isoformat(),
            "initial_model": initial_model,
            "signup_source": signup_source,
            "auth_method": auth_method
        })

    return users


def save_users(users):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "users.csv"

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=users[0].keys())
        writer.writeheader()
        writer.writerows(users)

    print(f"Создан файл: {output_file}")
    print(f"Количество пользователей: {len(users)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_subscriptions(users):
    rng = random.Random(SEED + 1)
    subscriptions = []

    for user in users:

        # Пропускаем пользователей с лицензией
        if user["initial_model"] != "subscription":
            continue

        # Вероятность оформления подписки - 80%
        if rng.random() >= 0.8:
            continue

        # Получаем дату регистрации
        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        # Генерируем задержку оформления
        delay = timedelta(
            days=rng.randint(0, 30),
            hours=rng.randint(0, 23)
        )

        created_at = registered_at + delay

        # Не допускаем событий за пределами наблюдения
        if created_at >= OBSERVATION_END:
            continue

        subscriptions.append({
            "subscription_id": len(subscriptions) + 1,
            "user_id": user["user_id"],
            "created_at": created_at.isoformat()
        })

    return subscriptions


def save_subscriptions(subscriptions):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "subscriptions.csv"

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "subscription_id",
                "user_id",
                "created_at"
            ]
        )

        writer.writeheader()
        writer.writerows(subscriptions)

    print(f"Создан файл: {output_file}")
    print(f"Количество подписок: {len(subscriptions)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_payments(subscriptions):
    rng = random.Random(SEED + 2)
    payments = []

    for subscription in subscriptions:
        created_at = datetime.fromisoformat(
            subscription["created_at"]
        )

        # Задержка до первой попытки оплаты
        delay = timedelta(
            days=rng.randint(0, 14),
            hours=rng.randint(0, 23)
        )

        initiated_at = created_at + delay

        if initiated_at >= OBSERVATION_END:
            continue

        # Определяем результат оплаты
        status = (
            "confirmed"
            if rng.random() < 0.78
            else "failed"
        )

        # Дата подтверждения есть только у успешных платежей
        confirmed_at = None

        if status == "confirmed":
            confirmed_at = initiated_at + timedelta(
                minutes=rng.randint(1, 180)
            )

            if confirmed_at >= OBSERVATION_END:
                status = "pending"
                confirmed_at = None

        method = rng.choices(
            ["sbp", "crypto"],
            weights=[65, 35]
        )[0]

        payments.append({
            "payment_id": len(payments) + 1,
            "subscription_id": subscription["subscription_id"],
            "initiated_at": initiated_at.isoformat(),
            "confirmed_at": (
                confirmed_at.isoformat()
                if confirmed_at is not None
                else None
            ),
            "amount_usd": 50.00,
            "method": method,
            "status": status
        })

    return payments


def save_payments(payments):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "payments.csv"

    fieldnames = [
        "payment_id",
        "subscription_id",
        "initiated_at",
        "confirmed_at",
        "amount_usd",
        "method",
        "status"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(payments)

    print(f"Создан файл: {output_file}")
    print(f"Количество платежей: {len(payments)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_subscription_periods(payments):
    periods = []

    for payment in payments:

        # Период создаётся только после успешной оплаты
        if payment["status"] != "confirmed":
            continue

        starts_at = datetime.fromisoformat(
            payment["confirmed_at"]
        )

        ends_at = add_one_month(starts_at)

        periods.append({
            "period_id": len(periods) + 1,
            "subscription_id": payment["subscription_id"],
            "payment_id": payment["payment_id"],
            "period_no": 1,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "canceled_at": None
        })

    return periods


def save_subscription_periods(periods):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "subscription_periods.csv"

    fieldnames = [
        "period_id",
        "subscription_id",
        "payment_id",
        "period_no",
        "starts_at",
        "ends_at",
        "canceled_at"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(periods)

    print(f"Создан файл: {output_file}")
    print(f"Количество оплаченных периодов: {len(periods)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_activations(payments):
    rng = random.Random(SEED + 3)
    activations = []

    for payment in payments:

        # Активация возможна только после успешной оплаты
        if payment["status"] != "confirmed":
            continue

        confirmed_at = datetime.fromisoformat(
            payment["confirmed_at"]
        )

        # Запрос на активацию после оплаты
        requested_at = confirmed_at + timedelta(
            minutes=rng.randint(0, 5)
        )

        # Вероятность успешной активации
        success = rng.random() < 0.99

        if success:
            status = "completed"

            # Выбираем категорию продолжительности
            duration_type = rng.choices(
                ["fast", "medium", "slow"],
                weights=[85, 10, 5]
            )[0]

            if duration_type == "fast":
                minutes = rng.randint(15, 30)

            elif duration_type == "medium":
                minutes = rng.randint(31, 240)

            else:
                minutes = rng.randint(241, 1440)

            completed_at = requested_at + timedelta(
                minutes=minutes
            )

        else:
            status = "failed"
            completed_at = None

        activations.append({
            "activation_id": len(activations) + 1,
            "subscription_id": payment["subscription_id"],
            "requested_at": requested_at.isoformat(),
            "completed_at": (
                completed_at.isoformat()
                if completed_at is not None
                else None
            ),
            "status": status
        })

    return activations


def save_activations(activations):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "activations.csv"

    fieldnames = [
        "activation_id",
        "subscription_id",
        "requested_at",
        "completed_at",
        "status"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(activations)

    print(f"Создан файл: {output_file}")
    print(f"Количество активаций: {len(activations)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_setting_changes(activations, periods):
    rng = random.Random(SEED + 4)
    changes = []

    # Первые оплаченные периоды по ID подписки
    first_periods = {
        p["subscription_id"]: p
        for p in periods
        if p["period_no"] == 1
    }

    # Возможные комбинации настроек
    configurations = [
        (risk, mode)
        for risk in ["low", "medium", "high"]
        for mode in ["conservative", "balanced", "aggressive"]
    ]

    for activation in activations:
        if activation["status"] != "completed":
            continue

        # 35% пользователей изменяют настройки
        if rng.random() >= 0.35:
            continue

        subscription_id = activation["subscription_id"]
        period = first_periods[subscription_id]

        completed_at = datetime.fromisoformat(
            activation["completed_at"]
        )

        ends_at = datetime.fromisoformat(period["ends_at"])
        window_end = min(ends_at, OBSERVATION_END)

        available_seconds = int(
            (window_end - completed_at).total_seconds()
        )

        if available_seconds <= 1:
            continue

        # Количество изменений настроек
        n_changes = rng.choices(
            [1, 2, 3],
            weights=[70, 23, 7]
        )[0]

        n_changes = min(n_changes, available_seconds - 1)

        # Генерируем даты в хронологическом порядке
        offsets = sorted(
            rng.sample(range(1, available_seconds), n_changes)
        )

        current_settings = ("medium", "balanced")

        for offset in offsets:
            changed_at = completed_at + timedelta(
                seconds=offset
            )

            # Исключаем текущую комбинацию
            alternatives = [
                c for c in configurations
                if c != current_settings
            ]

            current_settings = rng.choice(alternatives)

            changes.append({
                "change_id": len(changes) + 1,
                "subscription_id": subscription_id,
                "changed_at": changed_at.isoformat(),
                "risk_level": current_settings[0],
                "trading_mode": current_settings[1]
            })

    return changes


def save_setting_changes(changes):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "setting_changes.csv"

    fieldnames = [
        "change_id",
        "subscription_id",
        "changed_at",
        "risk_level",
        "trading_mode"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(changes)

    print(f"Создан файл: {output_file}")
    print(f"Количество изменений: {len(changes)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_incidents():
    rng = random.Random(SEED + 5)
    incidents = []

    n_incidents = 70

    # Не генерируем инциденты в последние двое суток
    latest_start = OBSERVATION_END - timedelta(days=2)

    total_seconds = int(
        (latest_start - REGISTRATION_START).total_seconds()
    )

    categories = [
        "trading_engine",
        "vps",
        "connectivity",
        "dashboard",
        "updates"
    ]

    for _ in range(n_incidents):

        # Случайное начало инцидента
        offset = rng.randrange(total_seconds)

        started_at = REGISTRATION_START + timedelta(
            seconds=offset
        )

        # Критичность инцидента
        severity = rng.choices(
            ["low", "medium", "high", "critical"],
            weights=[50, 30, 15, 5]
        )[0]

        # Продолжительность зависит от критичности
        duration_ranges = {
            "low": (10, 60),
            "medium": (30, 180),
            "high": (60, 480),
            "critical": (120, 1440)
        }

        min_minutes, max_minutes = duration_ranges[severity]

        duration = rng.randint(
            min_minutes, max_minutes
        )

        resolved_at = started_at + timedelta(
            minutes=duration
        )

        category = rng.choice(categories)

        incidents.append({
            "started_at": started_at.isoformat(),
            "resolved_at": resolved_at.isoformat(),
            "severity": severity,
            "category": category
        })

    # Сортировка по времени начала
    incidents.sort(key=lambda x: x["started_at"])

    # Присваиваем ID в хронологическом порядке
    for incident_id, incident in enumerate(incidents, start=1):
        incident["incident_id"] = incident_id

    return incidents


def save_incidents(incidents):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "incidents.csv"

    fieldnames = [
        "incident_id",
        "started_at",
        "resolved_at",
        "severity",
        "category"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file, fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(incidents)

    print(f"Создан файл: {output_file}")
    print(f"Количество инцидентов: {len(incidents)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_incident_impacts(incidents, activations, periods):
    rng = random.Random(SEED + 6)
    impacts = []

    # Собираем оплаченные периоды каждой подписки
    active_periods = {}

    for period in periods:
        subscription_id = period["subscription_id"]

        starts_at = datetime.fromisoformat(period["starts_at"])
        ends_at = datetime.fromisoformat(period["ends_at"])

        # Учитываем досрочную отмену, если она есть
        if period["canceled_at"] is not None:
            canceled_at = datetime.fromisoformat(
                period["canceled_at"]
            )
            ends_at = min(ends_at, canceled_at)

        active_periods.setdefault(
            subscription_id, []
        ).append((starts_at, ends_at))

    # Оставляем только успешные активации
    activated = {}

    for activation in activations:
        if activation["status"] == "completed":
            activated[activation["subscription_id"]] = (
                datetime.fromisoformat(
                    activation["completed_at"]
                )
            )

    impact_rates = {
        "low": 0.05,
        "medium": 0.15,
        "high": 0.35,
        "critical": 0.70
    }

    for incident in incidents:
        incident_start = datetime.fromisoformat(
            incident["started_at"]
        )

        incident_end = datetime.fromisoformat(
            incident["resolved_at"]
        )

        probability = impact_rates[incident["severity"]]

        for subscription_id, activated_at in activated.items():

            affected_at = None

            # Ищем пересечение инцидента и оплаченного доступа
            for period_start, period_end in active_periods.get(
                subscription_id, []
            ):
                overlap_start = max(
                    incident_start,
                    activated_at,
                    period_start
                )

                overlap_end = min(
                    incident_end,
                    period_end,
                    OBSERVATION_END
                )

                if overlap_start < overlap_end:
                    affected_at = overlap_start
                    break

            if affected_at is None:
                continue

            # Определяем, затронул ли сбой подписчика
            pair_rng = random.Random(
                f"{SEED + 6}:{incident['incident_id']}:{subscription_id}"
            )

            if pair_rng.random() >= probability:
                continue

            impacts.append({
                "impact_id": len(impacts) + 1,
                "incident_id": incident["incident_id"],
                "subscription_id": subscription_id,
                "affected_at": affected_at.isoformat(),
                "restored_at": incident_end.isoformat()
            })

    return impacts


def save_incident_impacts(impacts):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "incident_impacts.csv"

    fieldnames = [
        "impact_id",
        "incident_id",
        "subscription_id",
        "affected_at",
        "restored_at"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(impacts)

    print(f"Создан файл: {output_file}")
    print(f"Количество воздействий: {len(impacts)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_support_tickets(payments, activations, impacts, periods):
    rng = random.Random(SEED + 7)
    tickets = []

    def add_ticket(subscription_id, opened_at, category):
        if opened_at >= OBSERVATION_END:
            return

        resolution_time = timedelta(
            hours=rng.randint(1, 48),
            minutes=rng.randint(0, 59)
        )

        closed_at = opened_at + resolution_time

        # Если закрытие за пределами наблюдения,
        # обращение остаётся открытым
        if closed_at >= OBSERVATION_END:
            closed_at = None

        tickets.append({
            "subscription_id": subscription_id,
            "opened_at": opened_at.isoformat(),
            "closed_at": (
                closed_at.isoformat()
                if closed_at is not None
                else None
            ),
            "category": category
        })

    # 1. Обращения по оплате
    for payment in payments:
        if payment["status"] == "failed" and rng.random() < 0.20:
            opened_at = datetime.fromisoformat(
                payment["initiated_at"]
            ) + timedelta(minutes=rng.randint(5, 120))

            add_ticket(
                payment["subscription_id"],
                opened_at,
                "payment"
            )

    # 2. Обращения по активации
    for activation in activations:
        probability = (
            0.70 if activation["status"] == "failed"
            else 0.08
        )

        if rng.random() < probability:
            opened_at = datetime.fromisoformat(
                activation["requested_at"]
            ) + timedelta(minutes=rng.randint(5, 30))

            add_ticket(
                activation["subscription_id"],
                opened_at,
                "activation"
            )

    # 3. Обращения из-за инцидентов
    for impact in impacts:
        if rng.random() >= 0.22:
            continue

        affected_at = datetime.fromisoformat(
            impact["affected_at"]
        )
        restored_at = datetime.fromisoformat(
            impact["restored_at"]
        )

        duration_seconds = int(
            (restored_at - affected_at).total_seconds()
        )

        delay = rng.randrange(
            min(600, duration_seconds)
        ) if duration_seconds > 0 else 0

        add_ticket(
            impact["subscription_id"],
            affected_at + timedelta(seconds=delay),
            "technical"
        )

    # 4. Общие обращения
    first_periods = {
        p["subscription_id"]: p
        for p in periods
        if p["period_no"] == 1
    }

    for activation in activations:
        if activation["status"] != "completed":
            continue

        if rng.random() >= 0.12:
            continue

        subscription_id = activation["subscription_id"]
        period = first_periods[subscription_id]

        start = datetime.fromisoformat(
            activation["completed_at"]
        )
        end = min(
            datetime.fromisoformat(period["ends_at"]),
            OBSERVATION_END
        )

        if period["canceled_at"] is not None:
            end = min(
                end,
                datetime.fromisoformat(period["canceled_at"])
            )

        available_seconds = int((end - start).total_seconds())

        if available_seconds <= 0:
            continue

        opened_at = start + timedelta(
            seconds=rng.randrange(available_seconds)
        )

        add_ticket(subscription_id, opened_at, "general")

    # Сортируем обращения по дате
    tickets.sort(key=lambda t: t["opened_at"])

    for ticket_id, ticket in enumerate(tickets, start=1):
        ticket["ticket_id"] = ticket_id

    return tickets


def save_support_tickets(tickets):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "support_tickets.csv"

    fieldnames = [
        "ticket_id",
        "subscription_id",
        "opened_at",
        "closed_at",
        "category"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(tickets)

    print(f"Создан файл: {output_file}")
    print(f"Количество обращений: {len(tickets)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_license_purchases(users):
    rng = random.Random(SEED + 8)
    purchases = []

    for user in users:

        # Рассматриваем только лицензионную модель
        if user["initial_model"] != "license":
            continue

        # Вероятность покупки лицензии — 70%
        if rng.random() >= 0.70:
            continue

        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        # 85% покупателей приобретают лицензию
        # в течение первых 30 дней
        early_purchase = rng.random() < 0.85

        if early_purchase:
            delay_seconds = rng.randint(
                0, 30 * 24 * 60 * 60
            )
        else:
            delay_seconds = rng.randint(
                31 * 24 * 60 * 60,
                90 * 24 * 60 * 60
            )

        purchased_at = registered_at + timedelta(
            seconds=delay_seconds
        )

        if purchased_at >= OBSERVATION_END:
            continue

        purchases.append({
            "license_purchase_id": len(purchases) + 1,
            "user_id": user["user_id"],
            "purchased_at": purchased_at.isoformat(),
            "amount_usd": "550.00"
        })

    return purchases


def save_license_purchases(purchases):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "license_purchases.csv"

    fieldnames = [
        "license_purchase_id",
        "user_id",
        "purchased_at",
        "amount_usd"
    ]

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(purchases)

    print(f"Создан файл: {output_file}")
    print(f"Количество покупок лицензий: {len(purchases)}")

# ---------------------------------------------------------------------------------------------------------------------

def generate_first_renewals(
    payments, periods, activations, changes, impacts
):
    rng = random.Random(SEED + 9)

    activations_by_sub = {
        a["subscription_id"]: a
        for a in activations
    }

    changes_by_sub = {}

    for change in changes:
        subscription_id = change["subscription_id"]

        changes_by_sub.setdefault(
            subscription_id, []
        ).append(
            datetime.fromisoformat(change["changed_at"])
        )

    impacts_by_sub = {}

    for impact in impacts:
        subscription_id = impact["subscription_id"]

        impacts_by_sub.setdefault(
            subscription_id, []
        ).append(
            datetime.fromisoformat(impact["affected_at"])
        )

    first_periods = [
        p for p in periods if p["period_no"] == 1
    ]

    eligible = 0
    renewed = 0 

    for period in first_periods:
        subscription_id = period["subscription_id"]
        ends_at = datetime.fromisoformat(
            period["ends_at"]
        )

        # Не оцениваем ещё не завершившиеся периоды
        if ends_at >= OBSERVATION_END:
            continue

        eligible += 1
        # Момент подтверждения продления
        confirmed_at = ends_at - timedelta(
            hours=rng.randint(1, 72)
        )

        # Момент инициирования оплаты
        initiated_at = confirmed_at - timedelta(
            minutes=rng.randint(1, 120)
        )
        activation = activations_by_sub[subscription_id]

        if activation["status"] != "completed":
            renewal_probability = 0.04

        else:
            renewal_probability = 0.68

            requested_at = datetime.fromisoformat(
                activation["requested_at"]
            )
            completed_at = datetime.fromisoformat(
                activation["completed_at"]
            )

            duration_minutes = (
                completed_at - requested_at
            ).total_seconds() / 60

            if duration_minutes > 240:
                renewal_probability -= 0.12
            elif duration_minutes > 30:
                renewal_probability -= 0.05

            # Учитываем только инциденты до оплаты
            if any(
                t <= initiated_at
                for t in impacts_by_sub.get(subscription_id, [])
            ):
                renewal_probability -= 0.10

            # Учитываем только изменения настроек до оплаты
            if any(
                t <= initiated_at
                for t in changes_by_sub.get(subscription_id, [])
            ):
                renewal_probability += 0.08


        renewal_probability = max(
            0.02, min(0.95, renewal_probability)
        )

        if rng.random() >= renewal_probability:
            continue

        payment_id = len(payments) + 1

        payments.append({
            "payment_id": payment_id,
            "subscription_id": subscription_id,
            "initiated_at": initiated_at.isoformat(),
            "confirmed_at": confirmed_at.isoformat(),
            "amount_usd": "50.00",
            "method": rng.choices(
                ["sbp", "crypto"],
                weights=[65, 35]
            )[0],
            "status": "confirmed"
        })

        # Второй период начинается после первого
        periods.append({
            "period_id": len(periods) + 1,
            "subscription_id": subscription_id,
            "payment_id": payment_id,
            "period_no": 2,
            "starts_at": ends_at.isoformat(),
            "ends_at": add_one_month(ends_at).isoformat(),
            "canceled_at": None
        })

        renewed += 1

    return eligible, renewed

# ---------------------------------------------------------------------------------------------------------------------

def generate_later_renewals(payments, periods):
    rng = random.Random(SEED + 10)

    # Начинаем с пользователей, оплативших второй период
    last_periods = [
        p for p in periods if p["period_no"] == 2
    ]

    eligible = 0
    renewed = 0

    while last_periods:
        next_periods = []

        for previous in last_periods:
            ends_at = datetime.fromisoformat(
                previous["ends_at"]
            )

            if ends_at >= OBSERVATION_END:
                continue

            eligible += 1

            # Вероятность последующего продления
            if rng.random() >= 0.78:
                continue

            confirmed_at = ends_at - timedelta(
                hours=rng.randint(1, 48)
            )

            initiated_at = confirmed_at - timedelta(
                minutes=rng.randint(1, 120)
            )

            payment_id = len(payments) + 1

            payments.append({
                "payment_id": payment_id,
                "subscription_id": previous["subscription_id"],
                "initiated_at": initiated_at.isoformat(),
                "confirmed_at": confirmed_at.isoformat(),
                "amount_usd": "50.00",
                "method": rng.choices(
                    ["sbp", "crypto"],
                    weights=[65, 35]
                )[0],
                "status": "confirmed"
            })

            new_period = {
                "period_id": len(periods) + 1,
                "subscription_id": previous["subscription_id"],
                "payment_id": payment_id,
                "period_no": previous["period_no"] + 1,
                "starts_at": ends_at.isoformat(),
                "ends_at": add_one_month(ends_at).isoformat(),
                "canceled_at": None
            }

            periods.append(new_period)
            next_periods.append(new_period)

            renewed += 1

        # В следующей итерации обрабатываем новый месяц
        last_periods = next_periods

    return eligible, renewed

# ---------------------------------------------------------------------------------------------------------------------

def generate_reactivations(payments, periods, activations):
    rng = random.Random(SEED + 11)

    # Подписки с успешной технической активацией
    activated_subs = {
        a["subscription_id"]
        for a in activations
        if a["status"] == "completed"
    }

    # Находим последний оплаченный период каждой подписки
    last_periods = {}

    for period in periods:
        subscription_id = period["subscription_id"]

        if (
            subscription_id not in last_periods
            or period["period_no"]
            > last_periods[subscription_id]["period_no"]
        ):
            last_periods[subscription_id] = period

    eligible = 0
    reactivated = 0

    for subscription_id, previous in last_periods.items():

        # Не рассматриваем подписки без успешной активации
        if subscription_id not in activated_subs:
            continue

        previous_end = datetime.fromisoformat(
            previous["ends_at"]
        )

        # Если после окончания периода прошло меньше 7 дней,
        # мы пока не можем наблюдать реактивацию
        if (
            previous_end + timedelta(days=7)
            >= OBSERVATION_END
        ):
            continue

        eligible += 1

        # Вероятность возвращения — 20%
        if rng.random() >= 0.20:
            continue

        # Перерыв от 7 до 90 дней
        gap = timedelta(
            days=rng.randint(7, 90),
            hours=rng.randint(0, 23)
        )

        confirmed_at = previous_end + gap

        # Не создаём оплаты за пределами наблюдения
        if confirmed_at >= OBSERVATION_END:
            continue

        initiated_at = confirmed_at - timedelta(
            minutes=rng.randint(1, 120)
        )

        payment_id = len(payments) + 1

        payments.append({
            "payment_id": payment_id,
            "subscription_id": subscription_id,
            "initiated_at": initiated_at.isoformat(),
            "confirmed_at": confirmed_at.isoformat(),
            "amount_usd": "50.00",
            "method": rng.choices(
                ["sbp", "crypto"],
                weights=[65, 35]
            )[0],
            "status": "confirmed"
        })

        # Создаём новый оплаченный период после перерыва
        periods.append({
            "period_id": len(periods) + 1,
            "subscription_id": subscription_id,
            "payment_id": payment_id,
            "period_no": previous["period_no"] + 1,
            "starts_at": confirmed_at.isoformat(),
            "ends_at": add_one_month(confirmed_at).isoformat(),
            "canceled_at": None
        })

        reactivated += 1

    return eligible, reactivated

# ---------------------------------------------------------------------------------------------------------------------

def print_generation_report(
    eligible,
    renewed,
    later_eligible,
    later_renewed,
    reactivation_eligible,
    reactivated,
    payments,
    periods,
    post_eligible,
    post_renewed
):
    print("\n=== ЖИЗНЕННЫЙ ЦИКЛ ПОДПИСОК ===")

    print("\nПервое продление:")
    print("Подписок для оценки:", eligible)
    print("Первых продлений:", renewed)
    print("First Renewal Rate:", f"{renewed / eligible:.2%}")

    print("\nПоследующие продления:")
    print("Возможностей продления:", later_eligible)
    print("Последующих продлений:", later_renewed)

    if later_eligible > 0:
        print(
            "Subsequent Renewal Rate:",
            f"{later_renewed / later_eligible:.2%}"
        )

    print("\nРеактивации:")
    print("Подписок для оценки:", reactivation_eligible)
    print("Реактиваций:", reactivated)

    if reactivation_eligible > 0:
        print(
            "Observed Reactivation Rate:",
            f"{reactivated / reactivation_eligible:.2%}"
        )

    print("\nПродления после реактивации:")
    print("Возможностей продления:", post_eligible)
    print("Успешных продлений:", post_renewed)

    if post_eligible > 0:
        print(
            "Post-reactivation Renewal Rate:",
            f"{post_renewed / post_eligible:.2%}"
        )

    print("\nИтог:")
    print("Всего платежей:", len(payments))
    print("Всего оплаченных периодов:", len(periods))

# ---------------------------------------------------------------------------------------------------------------------

def generate_post_reactivation_renewals(payments, periods):
    rng = random.Random(SEED + 12)

    # Собираем все периоды по подпискам
    periods_by_sub = {}

    for period in periods:
        periods_by_sub.setdefault(
            period["subscription_id"], []
        ).append(period)

    # Находим периоды, начавшиеся после перерыва
    reactivated_periods = []

    for subscription_periods in periods_by_sub.values():
        subscription_periods.sort(
            key=lambda p: p["period_no"]
        )

        for previous, current in zip(
            subscription_periods,
            subscription_periods[1:]
        ):
            previous_end = datetime.fromisoformat(
                previous["ends_at"]
            )
            current_start = datetime.fromisoformat(
                current["starts_at"]
            )

            if current_start > previous_end:
                reactivated_periods.append(current)

    eligible = 0
    renewed = 0

    # Продлеваем подписки после возвращения
    active_chain = reactivated_periods

    while active_chain:
        next_chain = []

        for previous in active_chain:
            ends_at = datetime.fromisoformat(
                previous["ends_at"]
            )

            if ends_at >= OBSERVATION_END:
                continue

            eligible += 1

            # Вероятность продления — 78%
            if rng.random() >= 0.78:
                continue

            confirmed_at = ends_at - timedelta(
                hours=rng.randint(1, 48)
            )

            initiated_at = confirmed_at - timedelta(
                minutes=rng.randint(1, 120)
            )

            payment_id = len(payments) + 1

            payments.append({
                "payment_id": payment_id,
                "subscription_id": previous["subscription_id"],
                "initiated_at": initiated_at.isoformat(),
                "confirmed_at": confirmed_at.isoformat(),
                "amount_usd": "50.00",
                "method": rng.choices(
                    ["sbp", "crypto"],
                    weights=[65, 35]
                )[0],
                "status": "confirmed"
            })

            new_period = {
                "period_id": len(periods) + 1,
                "subscription_id": previous["subscription_id"],
                "payment_id": payment_id,
                "period_no": previous["period_no"] + 1,
                "starts_at": ends_at.isoformat(),
                "ends_at": add_one_month(ends_at).isoformat(),
                "canceled_at": None
            }

            periods.append(new_period)
            next_chain.append(new_period)

            renewed += 1

        active_chain = next_chain

    return eligible, renewed

# ---------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Генерация пользователей
    users = generate_users()
    save_users(users)

    # Генерация подписок
    subscriptions = generate_subscriptions(users)
    save_subscriptions(subscriptions)

    # Проверка уникальности подписок
    assert len(subscriptions) == len(
        {s["user_id"] for s in subscriptions}
    ), "Найдены повторные подписки"

    # Проверка дат создания подписок
    registration_dates = {
        u["user_id"]: datetime.fromisoformat(u["registered_at"])
        for u in users
    }

    assert all(
        registration_dates[s["user_id"]]
        <= datetime.fromisoformat(s["created_at"])
        < OBSERVATION_END
        for s in subscriptions
    ), "Обнаружены некорректные даты подписок"

    print("Все проверки подписок пройдены")

    payments = generate_payments(subscriptions)
    save_payments(payments)
    payment_stats = Counter(
        p["status"] for p in payments
    )

    print("Статусы платежей:", payment_stats)


    # Проверяем корректность статусов платежей
    assert all(
        (p["status"] == "confirmed") ==
        (p["confirmed_at"] is not None)
        for p in payments
    ), "Некорректные статусы платежей"

    # Pending допускается только для недавних платежей
    pending_payments = [
        p for p in payments
        if p["status"] == "pending"
    ]

    assert all(
        OBSERVATION_END - timedelta(hours=24)
        <= datetime.fromisoformat(p["initiated_at"])
        < OBSERVATION_END
        for p in pending_payments
    ), "Обнаружены устаревшие pending-платежи"

    print("Все проверки платежей пройдены")

    
    periods = generate_subscription_periods(payments)
    save_subscription_periods(periods)

    # Число первых периодов равно числу успешных оплат
    confirmed_count = sum(
        p["status"] == "confirmed"
        for p in payments
    )

    assert len(periods) == confirmed_count

    # Один период — один уникальный платёж
    assert len(periods) == len({
        p["payment_id"] for p in periods
    })

    # Проверяем продолжительность периодов
    assert all(
        datetime.fromisoformat(p["ends_at"])
        == add_one_month(datetime.fromisoformat(p["starts_at"]))
        for p in periods
    )

    print("Все проверки оплаченных периодов пройдены")


    # Генерация активаций
    activations = generate_activations(payments)
    save_activations(activations)

    # Статистика статусов
    activation_stats = Counter(
        a["status"] for a in activations
    )

    print("Статусы активаций:", activation_stats)

    # Проверка уникальности подписок
    assert len(activations) == len({
        a["subscription_id"] for a in activations
    }), "Обнаружены повторные активации"

    # Проверка статусов
    assert all(
        (a["status"] == "completed") ==
        (a["completed_at"] is not None)
        for a in activations
    ), "Некорректные статусы активаций"

    # Проверка дат успешных активаций
    assert all(
        datetime.fromisoformat(a["requested_at"])
        <= datetime.fromisoformat(a["completed_at"])
        < OBSERVATION_END
        for a in activations
        if a["status"] == "completed"
    ), "Обнаружены некорректные даты активаций"

    print("Все проверки активаций пройдены")


    changes = generate_setting_changes(activations, periods)
    save_setting_changes(changes)

    users_with_changes = len({
        c["subscription_id"] for c in changes
    })

    completed_count = sum(
        a["status"] == "completed"
        for a in activations
    )

    print("Пользователей, изменивших настройки:",
          users_with_changes)

    print("Доля активированных пользователей:",
          f"{users_with_changes / completed_count:.2%}")

    # Проверяем идентификаторы событий
    assert len(changes) == len({
        c["change_id"] for c in changes
    })

    # Проверяем допустимые значения
    assert all(
        c["risk_level"] in ["low", "medium", "high"]
        and c["trading_mode"] in [
            "conservative", "balanced", "aggressive"
        ]
        for c in changes
    )

    print("Все проверки изменений настроек пройдены")

    # Генерация технических инцидентов
    incidents = generate_incidents()
    save_incidents(incidents)

    # Распределение по критичности
    incident_stats = Counter(
        i["severity"] for i in incidents
    )

    print("Критичность инцидентов:", incident_stats)

    # Проверка уникальности ID
    assert len(incidents) == len({
        i["incident_id"] for i in incidents
    })

    # Проверка корректности дат
    assert all(
        datetime.fromisoformat(i["started_at"])
        < datetime.fromisoformat(i["resolved_at"])
        < OBSERVATION_END
        for i in incidents
    )

    print("Все проверки инцидентов пройдены")


    impacts = generate_incident_impacts(
        incidents, activations, periods
    )

    save_incident_impacts(impacts)

    print(
        "Затронуто уникальных подписок:",
        len({i["subscription_id"] for i in impacts})
    )

    print(
        "Инцидентов с пострадавшими:",
        len({i["incident_id"] for i in impacts})
    )

    # Одна подписка не может дважды фигурировать
    # в рамках одного инцидента
    assert len(impacts) == len({
        (i["incident_id"], i["subscription_id"])
        for i in impacts
    })

    # Проверяем связи и хронологию
    incidents_by_id = {
        i["incident_id"]: i for i in incidents
    }

    subscription_ids = {
        s["subscription_id"] for s in subscriptions
    }

    assert all(
        i["subscription_id"] in subscription_ids
        and i["incident_id"] in incidents_by_id
        and datetime.fromisoformat(i["affected_at"])
            >= datetime.fromisoformat(
                incidents_by_id[i["incident_id"]]["started_at"]
            )
        and datetime.fromisoformat(i["affected_at"])
            < datetime.fromisoformat(i["restored_at"])
        and datetime.fromisoformat(i["restored_at"])
            == datetime.fromisoformat(
                incidents_by_id[i["incident_id"]]["resolved_at"]
            )
        for i in impacts
    )

    print("Все проверки воздействий пройдены")

    # Первое продление подписок
    eligible, renewed = generate_first_renewals(
        payments, periods, activations, changes, impacts
    )

    # Третьи и последующие оплаченные периоды
    later_eligible, later_renewed = generate_later_renewals(
        payments, periods
    )

    # Реактивации после перерыва
    reactivation_eligible, reactivated = generate_reactivations(
        payments, periods, activations
    )

    # Проверяем, что каждый период имеет успешную оплату
    confirmed_payments = {
        p["payment_id"]: p
        for p in payments
        if p["status"] == "confirmed"
    }

    assert len(periods) == len(confirmed_payments)

    assert all(
        period["payment_id"] in confirmed_payments
        and confirmed_payments[period["payment_id"]][
            "subscription_id"
        ] == period["subscription_id"]
        for period in periods
    )

    # Проверяем, что периоды одной подписки не пересекаются
    periods_by_sub = {}

    for period in periods:
        periods_by_sub.setdefault(
            period["subscription_id"], []
        ).append(period)

    for subscription_periods in periods_by_sub.values():

        subscription_periods.sort(
            key=lambda p: p["starts_at"]
        )

        for previous, current in zip(
            subscription_periods,
            subscription_periods[1:]
        ):
            previous_end = datetime.fromisoformat(
                previous["ends_at"]
            )

            current_start = datetime.fromisoformat(
                current["starts_at"]
            )

            assert current_start >= previous_end, (
                "Обнаружено пересечение оплаченных периодов"
            )

    print("Все проверки реактиваций пройдены")

    # Продления после реактивации
    payments_before = len(payments)
    periods_before = len(periods)

    post_eligible, post_renewed = (
        generate_post_reactivation_renewals(
            payments, periods
        )
    )

    # Проверяем количество созданных записей
    assert len(payments) - payments_before == post_renewed
    assert len(periods) - periods_before == post_renewed

    print("Проверки продлений после реактивации пройдены")

    # Обновляем CSV после добавления продлений
    save_payments(payments)
    save_subscription_periods(periods)

    # Пересчитываем воздействия инцидентов
    impacts = generate_incident_impacts(
        incidents, activations, periods
    )
    save_incident_impacts(impacts)

    # Проверяем связи платежей и периодов
    assert len(periods) == sum(
        p["status"] == "confirmed" for p in payments
    )

    first_by_sub = {
        p["subscription_id"]: p
        for p in periods if p["period_no"] == 1
    }

    second_periods = [
        p for p in periods if p["period_no"] == 2
    ]

    # Второй период может начаться сразу после первого
    # или позднее, если пользователь реактивировал подписку
    assert all(
        datetime.fromisoformat(p["starts_at"])
        >= datetime.fromisoformat(
            first_by_sub[p["subscription_id"]]["ends_at"]
        )
        for p in second_periods
    ), "Обнаружено пересечение первого и второго периодов"

    # Проверяем число непрерывных первых продлений
    continuous_renewals = sum(
        p["starts_at"]
        == first_by_sub[p["subscription_id"]]["ends_at"]
        for p in second_periods
    )

    assert continuous_renewals == renewed, (
        "Количество первых продлений не совпадает"
    )

    # Далее идёт существующая генерация обращений
    tickets = generate_support_tickets(
        payments, activations, impacts, periods
    )


    tickets = generate_support_tickets(
        payments, activations, impacts, periods
    )

    save_support_tickets(tickets)

    print(
        "Обращения по категориям:",
        Counter(t["category"] for t in tickets)
    )

    subscription_created = {
        s["subscription_id"]: datetime.fromisoformat(
            s["created_at"]
        )
        for s in subscriptions
    }

    assert len(tickets) == len({
        t["ticket_id"] for t in tickets
    }), "Повторяющиеся ID обращений"

    for ticket in tickets:
        subscription_id = ticket["subscription_id"]

        assert subscription_id in subscription_created

        opened_at = datetime.fromisoformat(
            ticket["opened_at"]
        )

        assert (
            subscription_created[subscription_id]
            <= opened_at
            < OBSERVATION_END
        )

        if ticket["closed_at"] is not None:
            closed_at = datetime.fromisoformat(
                ticket["closed_at"]
            )

            assert opened_at <= closed_at < OBSERVATION_END

    print("Все проверки обращений пройдены")


    # Генерация покупок лицензий
    purchases = generate_license_purchases(users)
    save_license_purchases(purchases)

    # Проверяем уникальность покупателей
    assert len(purchases) == len({
        p["user_id"] for p in purchases
    }), "Обнаружены повторные покупки"

    users_by_id = {
        u["user_id"]: u for u in users
    }

    # Проверяем модель покупки, стоимость и даты
    for purchase in purchases:
        user = users_by_id[purchase["user_id"]]

        registered_at = datetime.fromisoformat(
            user["registered_at"]
        )

        purchased_at = datetime.fromisoformat(
            purchase["purchased_at"]
        )

        assert user["initial_model"] == "license"
        assert purchase["amount_usd"] == "550.00"
        assert registered_at <= purchased_at < OBSERVATION_END

    # Рассчитываем конверсию в покупку
    license_users = sum(
        u["initial_model"] == "license"
        for u in users
    )

    print(
        "Конверсия в покупку лицензии:",
        f"{len(purchases) / license_users:.2%}"
    )

    # Покупки в первые 30 дней
    early_purchases = sum(
        (
            datetime.fromisoformat(p["purchased_at"])
            - datetime.fromisoformat(
                users_by_id[p["user_id"]]["registered_at"]
            )
        ) <= timedelta(days=30)
        for p in purchases
    )

    print(
        "Покупок в первые 30 дней:",
        early_purchases
    )

    print("Все проверки покупок лицензий пройдены")

    # Итоговый отчёт по жизненному циклу подписок
    print_generation_report(
        eligible,
        renewed,
        later_eligible,
        later_renewed,
        reactivation_eligible,
        reactivated,
        payments,
        periods,
        post_eligible,
        post_renewed
    )

# ---------------------------------------------------------------------------------------------------------------------

print("Модели:", Counter(u["initial_model"] for u in users))
print("Источники:", Counter(u["signup_source"] for u in users))
print("Авторизация:", Counter(u["auth_method"] for u in users))