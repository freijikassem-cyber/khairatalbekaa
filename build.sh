#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
# Create the admin/login user, and keep its password in sync with the
# DJANGO_SUPERUSER_PASSWORD env var even if the user already exists.
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
  python manage.py shell <<'PYEOF'
import os
from django.contrib.auth import get_user_model
U = get_user_model()
name = os.environ["DJANGO_SUPERUSER_USERNAME"]
user, _ = U.objects.get_or_create(
    username=name,
    defaults={"email": os.environ.get("DJANGO_SUPERUSER_EMAIL", "")},
)
user.is_staff = True
user.is_superuser = True
user.set_password(os.environ["DJANGO_SUPERUSER_PASSWORD"])
user.save()
print(f"superuser '{name}' password synced")
PYEOF
fi
