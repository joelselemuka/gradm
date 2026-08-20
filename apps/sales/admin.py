from django.contrib import admin
from .models import Invoice, InvoiceLine, Payment

admin.site.register([Invoice, InvoiceLine, Payment])
