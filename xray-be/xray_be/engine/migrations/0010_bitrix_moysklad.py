from django.db import migrations, models
import django.db.models.deletion


def _fields():
    return [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("guest_session", models.CharField(blank=True, db_index=True, default="", max_length=128)),
        ("account", models.CharField(max_length=255)),
        ("token", models.TextField()),
        ("last_sync_at", models.DateTimeField(blank=True, null=True)),
        ("last_error", models.TextField(blank=True)),
        ("last_snapshot_id", models.CharField(blank=True, default="", max_length=64)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="engine.maxuser")),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("engine", "0009_deal_amount_wider"),
    ]

    operations = [
        migrations.CreateModel(
            name="BitrixConnection",
            fields=_fields(),
            options={"verbose_name": "Подключение Битрикс24", "verbose_name_plural": "Подключения Битрикс24"},
        ),
        migrations.CreateModel(
            name="MoySkladConnection",
            fields=_fields(),
            options={"verbose_name": "Подключение МойСклад", "verbose_name_plural": "Подключения МойСклад"},
        ),
    ]
