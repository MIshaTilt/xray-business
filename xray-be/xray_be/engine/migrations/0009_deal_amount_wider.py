from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("engine", "0008_amoconnection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deal",
            name="amount",
            field=models.DecimalField(decimal_places=2, max_digits=20),
        ),
    ]
