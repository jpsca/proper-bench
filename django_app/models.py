from django.db import models


class Fortune(models.Model):
    message = models.TextField()

    class Meta:
        db_table = "fortune"
        managed = False
