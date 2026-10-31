from collections import Counter
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Параметры генерации
SEED = 42
N_USERS = 10_000

REGISTRATION_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
REGISTRATION_END = datetime(2026, 7, 1, tzinfo=timezone.utc)
OBSERVATION_END = datetime(2026, 10, 1, tzinfo=timezone.utc)

# Путь для сохранения данных
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"


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


if __name__ == "__main__":
    users = generate_users()
    save_users(users)

print("Модели:", Counter(u["initial_model"] for u in users))
print("Источники:", Counter(u["signup_source"] for u in users))
print("Авторизация:", Counter(u["auth_method"] for u in users))