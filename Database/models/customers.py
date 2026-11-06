from mongoengine import (
    Document, StringField, IntField, FloatField
)

class Customer(Document):
    meta = {"collection": "customers"}

    customer_id = StringField(required=True, unique=True)
    name = StringField(required=True)

    recency = IntField(required=True, min_value=0)     # days
    frequency = IntField(required=True, min_value=0)   # number of purchases
    monetary = FloatField(required=True, min_value=0)  # total spent

    segment = StringField(
        choices=["VIP", "Loyal", "Regular", "At Risk", "Inactive", "Unclassified"],
        default="Unclassified"
    )