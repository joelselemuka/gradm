from celery import shared_task
from .services import send_general_report


@shared_task(autoretry_for=(Exception,),retry_backoff=True,max_retries=3)
def send_daily_sales_report():
    return send_general_report()
