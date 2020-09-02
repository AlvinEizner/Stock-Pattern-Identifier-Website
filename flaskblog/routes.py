import os
from flask import redirect, url_for, render_template, request, session, flash, g
from marshmallow import Schema, fields
from flaskblog import app, ma, bcrypt, login_manager, mail
from flaskblog.forms import RegForm, LoginForm, StockForm
from flask_login import login_user, current_user, logout_user, login_required, UserMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask_mail import Message

from azure.cosmos import exceptions, CosmosClient, PartitionKey
import json
from datetime import datetime
import requests
import uuid

import requests
import time
import datetime
import finnhub
import pandas as pd
import mplfinance as mpf
import matplotlib as plt
import base64
from io import BytesIO
from matplotlib.figure import Figure
finnhub_client = finnhub.Client(api_key="MYAPIKEY")

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


class User1(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        for i in range(0,len(users)):
            if users[i].id == user_id:
                return users[i]
    def __repr__(self):
        return f"User('{self.username}')"

users = []
cosmosinfo = container.query_items(query=f"SELECT * FROM TestContainer t where t.email <> 'hello'", enable_cross_partition_query=True)
for item in cosmosinfo:
    if item not in users:
        users.append(User1(id=item["id"], username=item["username"], password = item["password"]))

class UserSchema(ma.Schema):
    class Meta:
        fields = ('id', 'username', 'email', 'password')

user_schema = UserSchema()
users_schema = UserSchema(many = True)

@login_manager.user_loader
def load_user(user_id):
    user_arr = []
    cosmosinfo = container.query_items(query=f"SELECT * FROM gymAdmin", enable_cross_partition_query=True)
    for item in cosmosinfo:
        if item not in user_arr:
            user_arr.append(User1(id=item["id"], username=item["username"], password=item["password"]))
    for i in range(0, len(user_arr)):
        if user_arr[i].id == user_id:
            return user_arr[i]

@app.route("/", methods=["POST", "GET"])
@app.route("/home", methods=["POST", "GET"])
@login_required
def home():
    form = StockForm()
    result_arr = []
    img_arr = []
    del result_arr[:]
    del img_arr[:]
    if request.method == 'POST':
        ticker = form.stock.data
        today = int(time.time())
        one_month = 2678400
        res = finnhub_client.stock_candles(ticker.upper(), 'D', today - one_month, today)
        compare = finnhub_client.stock_candles(ticker.upper(), 'D', today - one_month - 345600, today - one_month + 345600)
        rf_comp = {}
        rf_comp['Date'] = []
        if compare["s"] != "no_data":
            for num in range(0, len(compare["c"])):
                rf_comp['Date'].append(datetime.datetime.fromtimestamp(compare["t"][num] + 28800).strftime('%Y-%m-%d'))
        rf = {}
        rf['Date'] = []
        rf['Open'] = []
        rf['High'] = []
        rf['Low'] = []
        rf['Close'] = []
        rf['Volume'] = []
        if res["s"] != "no_data":
            for num in range(0, len(res["c"])):
                rf['Date'].append(datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%Y-%m-%d'))
                rf['Open'].append(res["o"][num])
                rf['High'].append(res["h"][num])
                rf['Low'].append(res["l"][num])
                rf['Close'].append(res["c"][num])
                rf['Volume'].append(res["v"][num])
            pda = pd.DataFrame.from_dict(rf)
            pda['Date'] = pda['Date'].astype('datetime64[ns]')
            pda.index.name = 'Date'
            pda.set_index('Date', inplace=True)
            pda.shape
            pda.head(3)
            pda.tail(3)
            buf = BytesIO()
            mpf.plot(pda, type='candle', style='charles', title=ticker.upper(), savefig=buf)
            buf.seek(0)
            image = base64.b64encode(buf.getbuffer()).decode("ascii")
            img_arr.append(image)
            def check_ws():
                ws_count = 0
                green_candle = False
                downtrend_arr = []
                downtrend = False
                appender = []
                if len(appender) == 0:
                    for num in range(0, len(compare["c"])):
                        if compare["t"][num] == res["t"][0]:
                            appender.append(compare["c"][num-1])
                for num in range(0, len(res["c"])):
                    close_price = res["c"][num]
                    open_price = res["o"][num]
                    current_date = datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%m/%d/%Y')
                    if num == 0:
                        prev_price = appender[0]
                    if len(downtrend_arr) < 3:
                        downtrend_arr.append(close_price-prev_price)
                    if open_price < close_price:
                        green_candle = True
                    else:
                        if downtrend:
                            downtrend_arr.pop(0)
                            #downtrend = False
                            ws_count = 0
                            green_candle = False
                    if close_price >= prev_price and green_candle == True and downtrend == True:
                        ws_count += 1 
                    elif close_price < prev_price and num != 0 and downtrend == True:
                        for num in range(ws_count):
                            downtrend_arr.pop(0)
                        ws_count = 0
                    if len(downtrend_arr) == 3:
                        average = sum(downtrend_arr)/len(downtrend_arr)
                        if average < 0:
                            downtrend = True
                        elif ws_count > 0:
                            downtrend_arr.pop(0)
                        else:
                            downtrend_arr.pop(0)
                            downtrend = False 
                    if ws_count == 3:
                        downtrend = False
                        for num in range(1,len(downtrend_arr)):
                            downtrend_arr.pop(0)
                        result_arr.append('Third White Soldier on date ' + current_date)
                        print('Third White Soldier on date ' + current_date)
                        ws_count = 0
                    prev_price = close_price

            def check_bc():
                bc_count = 0
                red_candle = False
                uptrend_arr = []
                uptrend = False
                for num in range(0, len(res["c"])):
                    close_price = res["c"][num]
                    open_price = res["o"][num]
                    current_date = datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%m/%d/%Y')
                    if num == 0:
                        prev_price = close_price
                    if len(uptrend_arr) < 3:
                        uptrend_arr.append(close_price-prev_price)
                    if open_price > close_price:
                        red_candle = True
                    elif uptrend:
                        uptrend_arr.pop(0)
                        #uptrend = False
                        bc_count = 0
                        red_candle = False
                    if close_price <= prev_price and red_candle == True and uptrend == True:
                        bc_count += 1 
                    elif close_price > prev_price and num != 0 and uptrend == True:#double check this
                        for num in range(bc_count):
                            uptrend_arr.pop(0)
                        bc_count = 0
                    if len(uptrend_arr) == 3:
                        average = sum(uptrend_arr)/len(uptrend_arr)
                        if average > 0:
                            uptrend = True
                        elif average <= 0 and bc_count > 0:
                            uptrend_arr.pop(0)
                        else:
                            uptrend_arr.pop(0)
                            uptrend = False                
                    if bc_count == 3:
                        uptrend = False
                        for num in range(1,len(uptrend_arr)):
                            uptrend_arr.pop(0)
                        result_arr.append('Third Black Crow on date ' + current_date)
                        print('Third Black Crow on date ' + current_date)
                        bc_count = 0
                    prev_price = close_price

            def check_bearish_engulfing():
                uptrend_arr = []
                engulf_arr = []
                uptrend = False
                for num in range(0, len(res["c"])):
                    close_price = res["c"][num]
                    open_price = res["o"][num]
                    current_date = datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%m/%d/%Y')
                    if num == 0:
                        prev_price = close_price
                    if len(uptrend_arr) < 3:
                        uptrend_arr.append(close_price-prev_price)
                    if len(uptrend_arr) == 3:
                        average = sum(uptrend_arr)/len(uptrend_arr)
                        if average > 0:
                            uptrend = True
                        else:
                            uptrend_arr.pop(0)
                            uptrend = False
                    if open_price < close_price and uptrend == True: #checks if green candle
                        del engulf_arr[:]
                        engulf_arr.append(open_price)#open
                        engulf_arr.append(close_price)#close
                    elif len(engulf_arr) == 2 and open_price > close_price and uptrend == True:
                        if open_price > engulf_arr[1] and close_price < engulf_arr[0]:
                            result_arr.append('Bearish Engulfing at date: ' + current_date)
                            print('Bearish Engulfing at date: ' + current_date)
                            uptrend_arr.pop(0)
                            uptrend_arr.append(close_price-prev_price)
                        else:
                            del engulf_arr[:]
                            uptrend_arr.pop(0)
                            uptrend = False
                    elif open_price >= close_price and uptrend == True and len(engulf_arr) != 2:
                        uptrend_arr.pop(0)
                        uptrend = False
                        del engulf_arr[:]
                    else:
                        del engulf_arr[:]
                    prev_price = close_price

            def check_bullish_engulfing():
                downtrend_arr = []
                engulf_arr = []
                downtrend = False
                for num in range(0, len(res["c"])):
                    close_price = res["c"][num]
                    open_price = res["o"][num]
                    current_date = datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%m/%d/%Y')
                    if num == 0:
                        prev_price = close_price
                    if len(downtrend_arr) < 3:
                        downtrend_arr.append(close_price-prev_price)
                    if len(downtrend_arr) == 3:
                        average = sum(downtrend_arr)/len(downtrend_arr)
                        if average < 0:
                            downtrend = True
                        else:
                            downtrend_arr.pop(0)
                            downtrend = False
                    if open_price > close_price and downtrend == True: #checks if red candle
                        del engulf_arr[:]
                        engulf_arr.append(open_price)#open
                        engulf_arr.append(close_price)#close
                    elif len(engulf_arr) == 2 and open_price < close_price and downtrend == True:
                        if open_price < engulf_arr[1] and close_price > engulf_arr[0]:
                            result_arr.append('Bullish Engulfing at date: ' + current_date)
                            print('Bullish Engulfing at date: ' + current_date)
                            downtrend_arr.pop(0)
                            downtrend_arr.append(close_price-prev_price)
                        else:
                            del engulf_arr[:]
                            downtrend_arr.pop(0)
                            downtrend = False
                    elif open_price <= close_price and downtrend == True and len(engulf_arr) != 2:
                        downtrend_arr.pop(0)
                        downtrend = False
                        del engulf_arr[:]
                    else:
                        del engulf_arr[:]
                    prev_price = close_price

            def check_shstar():
                uptrend_arr = []
                uptrend = False
                wick = 0
                tail = 0
                for num in range(0, len(res["c"])):
                    close_price = res["c"][num]
                    open_price = res["o"][num]
                    current_date = datetime.datetime.fromtimestamp(res["t"][num] + 28800).strftime('%m/%d/%Y')
                    candle_bod = abs(close_price - open_price)
                    if num == 0:
                        prev_price = close_price
                    if len(uptrend_arr) < 3:
                        uptrend_arr.append(close_price-prev_price)
                    if len(uptrend_arr) == 3:
                        average = sum(uptrend_arr)/len(uptrend_arr)
                        if average > 0:
                            uptrend = True
                        else:
                            uptrend_arr.pop(0)
                            uptrend = False
                    if open_price < close_price: #checks if green candle
                        wick = res["h"][num] - close_price
                        tail = open_price - res["l"][num]
                    elif open_price > close_price: # checks if red candle
                        wick = res["h"][num] - open_price
                        tail = close_price - res["l"][num]
                    if wick >= 2 * candle_bod and wick >=2 * tail and uptrend:
                        result_arr.append('Shooting Star at date: ' + current_date)
                        print('Shooting Star at date: ' + current_date)
                    elif len(uptrend_arr) == 3:
                        uptrend = False
                        uptrend_arr.pop(0)
                    prev_price = close_price

            check_ws()
            check_bc()
            check_bearish_engulfing()
            check_bullish_engulfing()
            check_shstar()
    result = ", ".join(result_arr)
    img = "".join(img_arr)
    return render_template("index.html", form=form, result=result, img="".join(img_arr))


@app.route("/register", methods=["POST", "GET"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        container.create_item(body={'id' : form.username.data + '_' + str(uuid.uuid4()),
                                    'username' : form.username.data,
                                    'password' : hashed_password
                                    })
        flash(f'Account generation successful! You are now able to log in!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        user = list(container.query_items(query=f"SELECT * FROM gymAdmin t WHERE t.username = '{username}'", enable_cross_partition_query=True))
        if len(user) == 1:
            usr = User1(user[0].get("id"), user[0].get("username"), user[0].get("password"))
        if len(user) == 1 and bcrypt.check_password_hash(user[0].get("password"), form.password.data):
            login_user(usr, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('You have been logged in!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login unsucessful. Please check email and/or password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout", methods=["POST", "GET"])
def logout():
    logout_user()
    flash(f"Logout Successful!", "info")
    return redirect(url_for('login'))

@app.route("/account")
@login_required
def account():
    return render_template("account.html", title='Account')

@app.route("/about")
@login_required
def about():
    return render_template("about.html", title='About')
