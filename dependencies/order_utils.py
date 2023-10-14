import datetime


def get_pretty_estimated_delivery_date(order_date: datetime.datetime) -> str:
    day_of_week = order_date.weekday()
    days_to_sunday: int
    if day_of_week < 3:
        days_to_sunday = 6 - day_of_week
    else:
        days_to_sunday = 7 + 6 - day_of_week
    estimated_delivery_date = order_date + datetime.timedelta(days=days_to_sunday)
    return estimated_delivery_date.strftime("%a, %b %d, %Y")
