
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from category.models import *

from faker import Faker

f=Faker()

for i in range(200):
    Cat=Categorie.objects.create(Name=f.email(),Status="Désactivé")
    Cat.save()


