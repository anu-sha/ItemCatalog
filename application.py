from flask import Flask, render_template, redirect, request, url_for,flash,jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
 
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random,string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from oauth2client.client import OAuth2Credentials
import httplib2
import json
from flask import make_response
import requests


app=Flask(__name__)

#client id used for Google authentication
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog"

engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

#creating session object
DBSession = sessionmaker(bind=engine)
session = DBSession()

#login route
@app.route('/login')
def showLoginPage():
    state=''.join(random.choice(string.ascii_uppercase+string.digits)for x in xrange(32))
    login_session['state']=state
    return render_template('login.html', STATE=state)

#google account login route handler
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate token-state
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
        credentials = oauth_flow.step2_exchange(code).to_json()
    except FlowExchangeError:
        #if there is an error authorizing return the failure message
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check if the access token is valid.
    access_token = OAuth2Credentials.from_json(credentials).access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'% access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = OAuth2Credentials.from_json(credentials).id_token['sub']
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

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': OAuth2Credentials.from_json(credentials).access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()
    #store the data i login_session object
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    
    #create the output string
    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("You are now logged in as %s" % login_session['username'])
    return output

#user functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

#get user info from id
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

#get userid from email
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/')
@app.route('/catalog')
def showCatalog():
    #get all catalog categories
    categories=session.query(Category).all()

    #get latest 10 added items
    items=session.query(Item).all()

    #pass in if user is logged in or not
    if 'username' in login_session:
        loggedIn=True
    else:
        loggedIn=False
    
    return render_template('catalog.html', categories=categories, items=items, loggedIn=loggedIn)


#handles showing items in a category
@app.route('/catalog/<string:category_title>/items')
def showCategoryItems(category_title):
    #get category that has the category_title
    categories=session.query(Category).all()
    category = session.query(Category).filter_by(name=category_title).first()
    print category.name
    #check if any value is returned
    if category is not None:
        items=session.query(Item).filter_by(category_id=category.id).all()
        #pass in if user is logged in or not
        if 'username' in login_session:
            loggedIn=True
        else:
            loggedIn=False
        #render category page    
        return render_template('category.html', categories=categories, category=category, items=items, loggedIn=loggedIn)
    else:
        return render_template('error.html', message='Category not found')


#handles showing item 
@app.route('/catalog/<string:category_title>/<string:item_title>')
def showItem(category_title,item_title):
    #get the item details from db
    item=session.query(Item).filter_by(name=item_title).one()
    #check if any item is returned
    if item is not None:
        #pass in if user is logged in or not
        if 'username' in login_session:
            loggedIn=True
        else:
            loggedIn=False
        return render_template('item.html', item=item, category=category_title, loggedIn=loggedIn)
    else:
        return render_template('error.html', message='Item not found')


#handles adding an item
@app.route('/catalog/item/add',methods=['GET','POST'])
def addItem():
    #check if request is get or post
    #pass in if user is logged in or not
    if 'username' in login_session:
        loggedIn=True
    else:
        loggedIn=False

        
     #get all categories to pass to the template
    categories=session.query(Category).all() 
    if request.method=='POST':
        #process the request only if the user is loggedin
        if loggedIn:
            #get the name and description from the form fields
            if request.form['name']:
                name=request.form['name']
            else:
                #return error is name is not entered
                return render_template('itemadd.html', categories=categories, loggedIn=loggedIn, error="One of the required fields is missing")
            if request.form['description']:
                description=request.form['description']

            
            
            category_id=request.form['option']
            #check if category is selected
            if category_id is not None:
                category=session.query(Category).filter_by(id=category_id).one()
                #add item
                item=Item(name=name,description=description,category=category, user_id=login_session['user_id'])
                session.add(item)
                session.commit()
                return redirect(url_for('showCategoryItems',category_title=category.name))
            else:
                #return error if category not selected
                return render_template('itemadd.html', categories=categories, loggedIn=loggedIn, error="One of the required fields is missing")
        else:
            #if user is not logged in return an error
            return render_template('itemadd.html', categories=categories, loggedIn=loggedIn, error="You are not authorized to add an item")
            
    else:
        #render the page with the info if it is a get request
       
        return render_template('itemadd.html', categories=categories, loggedIn=loggedIn)
                              

    
#handles editing an item
@app.route('/catalog/<string:item_title>/edit',methods=['GET','POST'])
def editItem(item_title):
    #get the item with the name passe
    item=session.query(Item).filter_by(name=item_title).one()
    #get all categories to pass to the template
    categories=session.query(Category).all() 
    #pass in if user is logged in or not
    if 'username' in login_session:
        loggedIn=True
    else:
        loggedIn=False
    #check if it is a post request
    #item should be saved if it is a post , the form should be displayed if it is a get request
    if request.method=='POST':
        #check of user is logged in and the user is the owner of the item
        if loggedIn and item.user_id == login_session['user_id']:
       
            #if a value has been entered for the item name
            if request.form['name']:
                item.name=request.form['name']
            #if a value has been entered for item description    
            if request.form['description']:
                item.description=request.form['description']
            print request.form['option']    
            #add the item to the session    
            session.add(item)
            session.commit()
            flash('Item Edited')
            #once item has been saved redirect back to the view showing the category items
            return redirect(url_for('showCategoryItems',category_title=item.category.name))
        else:
            return render_template('itemedit.html', categories=categories, item=item,category=item.category, loggedIn=loggedIn, error="You are not authorized to edit this record")
    else:
        #get all categories to pass to the template
        categories=session.query(Category).all()
        #if it is a get request display the edit form
        return render_template('itemedit.html',category=item.category, item=item, categories=categories, loggedIn=loggedIn)

    


@app.route('/catalog/<string:item_title>/delete', methods=['GET','POST'])
def deleteItem(item_title):
    #get the item with the name passe
    item=session.query(Item).filter_by(name=item_title).one()
    #pass in if user is logged in or not
    if 'username' in login_session:
        loggedIn=True
    else:
        loggedIn=False
    #check if it is a post request
    #item should be deleted if it is a post , the form should be displayed if it is a get request
    if request.method=='POST':
        if loggedIn and item.user_id == login_session['user_id']:
           #delete the item
            #get the categoryname before the item is deleted
            categoryname=item.category.name
            session.delete(item)
            session.commit()
            flash('Item Deleted')
            #once item has been deleted redirect back to the view showing the category items
            return redirect(url_for('showCategoryItems',category_title=categoryname))
        else:
            return render_template('itemdelete.html', item=item, loggedIn=loggedIn, error="You are not authorized to delete")
    else:
       
        #if it is a get request display the delete form
        return render_template('itemdelete.html', item=item, loggedIn=loggedIn)

#returns all categories in json format
@app.route('/categories.json')
def sendCategoriesJson():
    #get all categories 
    categories=session.query(Category).all()
    return jsonify(Categories=[category.serialize for category in categories])


#returns all the items in json format
@app.route('/items.json')
def sendItemsJson():
    #get all items 
    items=session.query(Item).all()
    return jsonify(Items=[item.serialize for item in items])


#returns all the items in a category in json format
@app.route('/catalog/<string:category_title>/items.json')
def sendCategoryItemsJson(category_title):
    #get category corresponding to category_title
    category=session.query(Category).filter_by(name=category_title).first()
    #if a category is returned from the db
    if category is not None:
        items=session.query(Item).filter_by(category_id=category.id).all()
        return jsonify(Items=[item.serialize for item in items])
    else:
       return render_template('error.html', message='Category not found')
    

#handles logout
@app.route('/disconnect')
def logout():
    access_token = OAuth2Credentials.from_json(login_session['credentials']).access_token
    #print 'In gdisconnect access token is %s', % access_token
     
    print login_session['username']
    if access_token is None:
 	print 'Access Token is None'
    	response = make_response(json.dumps('Current user not connected.'), 401)
    	response.headers['Content-Type'] = 'application/json'
    	return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
	del login_session['credentials'] 
    	del login_session['gplus_id']
    	del login_session['username']
    	del login_session['email']
    	del login_session['picture']
    	response = make_response(json.dumps('Successfully disconnected.'), 200)
    	response.headers['Content-Type'] = 'application/json'
    	return redirect(url_for('showCatalog'))
    else:
	
    	response = make_response(json.dumps('Failed to revoke token for given user.', 400))
    	response.headers['Content-Type'] = 'application/json'
    	return response

if __name__=='__main__':
    app.secret_key='super_secret_key'
    app.debug= True
    app.run(host='0.0.0.0',port=5000)                           
