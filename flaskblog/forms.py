from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError

from azure.cosmos import exceptions, CosmosClient, PartitionKey
import json
from datetime import datetime
import requests
import uuid

# Initialize the Cosmos client
endpoint = "COSMOSENDPT"
key = 'MYKEY'
client = CosmosClient(endpoint, key)

# Initialize Database
database_name = "TestDatabase"
database = client.get_database_client(database=database_name)

# Initialize Container
container_name = "userInfo"
container = database.get_container_client(container_name)


class RegForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=15)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        query = f"SELECT * FROM TestContainer t WHERE t.username IN ('{username.data}')"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        if len(items) > 0:
            raise ValidationError('Username already in use. Please choose a new one')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class StockForm(FlaskForm):
    stock = StringField('Stock', validators=[DataRequired()])
    submit = SubmitField('Submit')






