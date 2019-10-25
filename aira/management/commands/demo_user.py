from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from aira.models import Agrifield, CropType, IrrigationLog, IrrigationType


class Command(BaseCommand):
    help = """Create demo user with credentials
              username: demo
              password: demo
           """

    def handle(self, *args, **options):
        demo, created = User.objects.get_or_create(
            username="demo", email="demo@aira.com"
        )
        demo.set_password("demo")
        demo.is_active = True
        demo.save()
        demo.profile.first_name = "Aira Demo"
        demo.profile.last_name = "Aira Demo"
        demo.profile.address = "Aira"
        demo.save()

        for item in settings.AIRA_DEMO_USER_INITIAL_AGRIFIELDS:
            f, created = Agrifield.objects.get_or_create(
                owner=demo,
                name=item["name"],
                location=Point(*item["coordinates"]),
                crop_type=CropType.objects.get(id=item["crop_type_id"]),
                irrigation_type=IrrigationType.objects.get(
                    id=item["irrigation_type_id"]
                ),
                area=item["area"],
                use_custom_parameters=False,
            )
            f.save()
            for irlog in item["irrigation_log"]:
                l, created = IrrigationLog.objects.get_or_create(
                    agrifield=f,
                    time=irlog["time"],
                    applied_water=irlog["applied_water"],
                )
                l.save()
        self.stdout.write("demo user created/updated successfully")
