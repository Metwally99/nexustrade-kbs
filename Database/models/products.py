from mongoengine import (
    Document, StringField, FloatField, IntField
)

class Product(Document):
    meta = {"collection": "products"}

    product_id = StringField(required=True, unique=True)
    name = StringField(required=True)

    stock = IntField(required=True)
    reorder_level = IntField(required=True)

    turnover = FloatField(required=True)  

    price = FloatField(required=True)
    margin = FloatField(required=True)  

    revenue = FloatField(required=True)
    revenue_delta = FloatField(required=True)  

    returns = FloatField(required=True)  
    cart_abandonment = FloatField(required=True)  