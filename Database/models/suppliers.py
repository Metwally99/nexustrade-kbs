from mongoengine import (
    Document, StringField, FloatField, IntField, BooleanField, ReferenceField
)
from Database.models.products import Product


class Supplier(Document):
    meta = {"collection": "suppliers"}

    supplier_id = StringField(required=True, unique=True)
    name = StringField(required=True)

    product = ReferenceField(Product, required=True)

    lead_time = IntField(required=True, min_value=0)  
    reliability = FloatField(required=True, min_value=0, max_value=100)  

    price_per_unit = FloatField(required=True, min_value=0)
    price_delta = FloatField()  

    bulk_available = BooleanField(default=False)
    single_source = BooleanField(default=False)