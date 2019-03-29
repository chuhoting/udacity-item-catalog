import requests
from flask import make_response, url_for, redirect, flash, jsonify
import json
import httplib2
from oauth2client.client import FlowExchangeError
from oauth2client.client import flow_from_clientsecrets
import string
import random
from flask import session as login_session
from databasecreate import SportCategory, Base, SportItems, User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from flask import Flask, render_template, request


app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog Application"

# Connect to Database and create database session
engine = create_engine('sqlite:///sportcategorysportitems.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# ===================
# Login Routing
# ===================

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps
                                 ('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # See if a user exists, if it doesn't make a new one

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '" style = "width: 300px height: 300px border-radius: 150px"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# User's Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
        # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('catalog'))

    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# ===================
#  Routing
# ===================
# Add JSON API Endpoint


@app.route('/catalog/JSON')
def catalogJSON():
    categories = session.query(SportCategory).all()
    items = session.query(SportItems).order_by(SportItems.id.desc()).limit(10)
    return jsonify(SportCategories=[c.serialize for c in categories],
                   SportLatestItems=[i.serialize for i in items])


@app.route('/catalog/<string:category_name>/<string:item_name>/JSON')
def descriptionofitemJSON(category_name, item_name):
    categoriesid = session.query(
        SportCategory).filter_by(name=category_name).one()
    itemsdescription = session.query(
        SportItems).filter_by(name=item_name).all()
    return jsonify(ItemDescriptions=[i.serialize for i in itemsdescription])


# Show all catalog - Homepage
@app.route('/')
@app.route('/catalog')
def catalog():
    categories = session.query(SportCategory).all()
    items = session.query(SportItems).order_by(SportItems.id.desc()).limit(10)
    quantity = items.count()
    joining = session.query(SportItems, SportCategory).join(
        SportCategory).order_by(SportItems.id.desc()).limit(10)
    if 'username' not in login_session:
        return render_template('catalog.html', categories=categories,
                               items=items, quantity=quantity, joining=joining)
    else:
        return render_template('cataloglogin.html', categories=categories,
                               items=items, quantity=quantity, joining=joining)


@app.route('/catalog/<string:category_name>/items')
def catalogbycategory(category_name):
    categories = session.query(SportCategory).all()
    categoriesid = session.query(
        SportCategory).filter_by(name=category_name).one()
    itemsfiltered = session.query(SportItems).filter_by(
        category_id=categoriesid.id).all()
    if 'username' not in login_session:
        return render_template('catalog2.html', categories=categories,
                               categoriesid=categoriesid,
                               itemsfiltered=itemsfiltered)
    else:
        return render_template('catalog2login.html', categories=categories,
                               categoriesid=categoriesid,
                               itemsfiltered=itemsfiltered)


@app.route('/catalog/<string:category_name>/<string:item_name>')
def descriptionofitem(category_name, item_name):
    categoriesid = session.query(
        SportCategory).filter_by(name=category_name).one()
    itemsdescription = session.query(
        SportItems).filter_by(name=item_name).all()
    if 'username' not in login_session:
        return render_template('Description.html', categoriesid=categoriesid,
                               itemsdescription=itemsdescription)
    else:
        return render_template('Descriptionlogin.html',
                               categoriesid=categoriesid,
                               itemsdescription=itemsdescription)


@app.route('/catalog/additem', methods=['GET', 'POST'])
def additems():
    categories = session.query(SportCategory).all()
    if 'username' not in login_session:
        return redirect('login')

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        newitem = SportItems(
            name=name, description=description, category_id=category,
            user_id=login_session['user_id'])
        session.add(newitem)
        session.commit()
        return redirect('/catalog')
    else:
        return render_template('add.html', categories=categories)


@app.route('/catalog/<string:delete_item>/delete', methods=['GET', 'POST'])
def descriptiondelete(delete_item):
    toberemoved = session.query(SportItems).filter_by(name=delete_item).one()
    if 'username' not in login_session:
        return redirect('login')

    if request.method == 'POST':
        session.delete(toberemoved)
        session.commit()
        return redirect('/catalog')
    else:
        return render_template('delete.html', toberemoved=toberemoved)


@app.route('/catalog/<string:edit_item>/edit', methods=['GET', 'POST'])
def editing(edit_item):
    categories = session.query(SportCategory).all()
    toedit = session.query(SportItems).filter_by(name=edit_item).one()
    categoriesitem = session.query(SportCategory).filter_by(
        id=toedit.category_id).one()
    data = session.query(SportCategory, SportItems).join(
        SportItems).filter_by(id=toedit.id).one()

    creator = getUserInfo(toedit.user_id)

    if 'username' not in login_session:
        return redirect('login')

    if creator.email != login_session['email']:
        return "<script>function myFunction(){alert('\
        Cannot edit item');}</script><body onload='myFunction()'>"

    if request.method == 'POST':
        if request.form['name']:
            toedit.name = request.form['name']
        if request.form['description']:
            toedit.description = request.form['description']
        if request.form['category']:
            toedit.category_id = request.form['category']
        session.add(toedit)
        session.commit()
        flash("Catalog item updated!", 'success')
        return redirect(url_for('catalog'))
    else:
        return render_template('edit.html', toedit=toedit,
                               categories=categories,
                               categoriesitem=categoriesitem,
                               data=data,
                               creator=creator)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000, threaded=False, debug=True)
