import webapp2
import jinja2
import os
import logging
import hashlib
import re

import urllib2
import json

from google.appengine.ext import db
from google.appengine.api import urlfetch

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3, 20}$")
PASS_RE = re.compile(r"^.{3,20}$")
int_list = []
topic_list = []
url_list = []

urlfetch.set_default_fetch_deadline(120)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def valid_username(username):
    #return username and USER_RE.match(username)
    return username

def valid_password(password):
    return password and PASS_RE.match(password)

def hashPass(password):
	#will add salt functionality
	return hashlib.md5(password).hexdigest()

def hashCookie(var1=''):
	return "%s|%s" %(var1, hashPass(var1))

def checkHash(variable=''):
	if (variable is None):
		return 0
	else:
		var1 = variable.split('|')[0]
		if hashCookie(var1) == variable:
			return var1

def topics():
    x = urllib2.urlopen('https://api.coursera.org/api/catalog.v1/categories').read()
    j = json.loads(x)
    global topic_list 
    topic_list = []
    for x in range(0, len(j['elements'])):
     	topic_list.append(j['elements'][x]['name'])

def urls():
    start = 'http://ajax.googleapis.com/ajax/services/search/images?v=1.0&q='
    urlQueries = []
    global url_list
    global topic_list
    for a in topic_list:
        m = a.split(' ')
        # if a == 'Social Sciences':
        # 	urlQueries.append('')
        urlQueries.append('%s%s' % (start, '%20'.join(m)))
    for url in urlQueries:
        x = urllib2.urlopen(url).read()
        j = json.loads(x)
        url_list.append( j['responseData']['results'][0]['url'])


def getPic(interest):
	urls()
	global url_list
	topics()
	global topic_list
	val = -1
	for x in range(0, len(topic_list)): 
		logging.info(url_list[x])
		if topic_list[x] == interest:
			val = x
			#logging.info('val = %s' % val)
	if val != -1:
		return url_list[val]
	else:
		return 'Empty'

class User(db.Model):
	username = db.StringProperty()
	password = db.StringProperty()
	name = db.StringProperty()
	idNum = db.IntegerProperty()
	school = db.StringProperty()
	grade = db.StringProperty()
	interest_list = db.ListProperty(db.Key)

	topics()
	def render_new_post(self):
		return render_str('new_post.html', topic_list=topic_list)

class Interest(db.Model):
	name = db.StringProperty()
	classes = db.TextProperty() 
	clubs = db.TextProperty() 
	competitions = db.TextProperty() 
	picUrl = db.StringProperty()

	def members (self):
		return Interest.gql("where user = :n", n=self.key())

	def render(self, num):
		return render_str("interest_table.html", int_list=int_list, num= num)

class Post (db.Model):
	title = db.StringProperty()
	content = db.TextProperty()
	created_time = db.DateTimeProperty(auto_now_add = True)
	interest = db.StringProperty()
	inputter = db.StringProperty() 
	club = db.BooleanProperty()
	picUrl = db.StringProperty()

	def render_post(self):
		return render_str('post.html', p = self)

class Club (db.Model):
	name = db.StringProperty()
	interests = db.StringListProperty()
	officers = db.StringListProperty()
	picUrl = db.StringProperty()

	def render_new_post(self):
		return render_str('new_post.html', topic_list=topic_list)

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def setCookie(self, var1):
        cook = hashCookie(var1)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.headers.add_header('set-cookie', 'user_id=%s;Path=/' % cook)

    def getCookie(self, name):
    	cookie_val = self.request.cookies.get(name)
        return cookie_val and checkHash(cookie_val)

    # def initialize(self, *a, **kw):
    # 	webapp2.RequestHandler.initialize(self, *a, **kw)
    #     uid = self.getCookie('user_id')
    #     self.user = uid and User.get_by_id(int(uid))

class MainHandler(Handler):
    def get(self):
        self.render('front.html')

class SelectInterestHandler(Handler):
    def get(self):
    	vari = self.request.cookies.get('user_id')
    	temp = checkHash(vari)
    	if temp:
        	topics()
        	#urls = self.urls(topics)
        	urls()
        	global int_list 
        	global topic_list
        	global url_list

        	for x in range(0, len(topic_list)):
        		a = Interest(name=topic_list[x], picUrl=url_list[x])
        		a.put()
        		int_list.append(a)
        		logging.info(int_list[x].name)
        	self.render('select_interest.html', int_list = int_list)
        else:
        	self.redirect('/signup')

    def post(self):
    	self.redirect('/pursue_interest')
        #self.redirect('/pursue_interest?name1=%s&name2=%s' %('mathematics','chemistry'))

class SignUpHandler(Handler):
    def get(self):
        self.render('signup.html')

    def checkErrors(self, username='', password='', vPassword='', name='', school=''):
        error = False
        params = dict (username= username, password = password, name= name)
        if not valid_username(username):
            params['err_user'] = 'Please input a valid username'
            error = True
        if not valid_password(password):
            params['err_pass'] = 'Please input a valid password'
            error = True
        elif vPassword != password:
            params['err_verify'] = "Passwords don't match"
            error = True
        if not name:
            params['err_name'] = "Please input your name"
            error = True
        if not school:
        	params['err_school'] = "Please choose your school"
        	error = True
        if error:
            self.render('/signup.html', **params)
        else:
            return 'valid'

    def accountExists(self, temp):
    	output = db.GqlQuery("Select * from User where filter = :name", name=temp.username)
    	if output is None:
    		return output

    def post(self):
     	username= self.request.get('username')
     	password = self.request.get('password')
     	vPassword = self.request.get('vPassword')
     	name = self.request.get('name')
     	school = self.request.get('school')
     	grade = self.request.get('grade')
     	idNum = self.request.get('idNum')

     	if self.checkErrors(username, password, vPassword, name, school):
    		temp = User(key_name= idNum, username=username, password=password, name=name, school=school, grade=grade)

    		if self.accountExists(temp):
    			self.render('signup.html', err1 = 'This account already exists.')
    		else:
    			vari = hashPass(password)
    			temp.password= vari
    			temp.put()
    			logging.info("the key will be %s" % temp.key().id())
    			self.setCookie(str(idNum)) 
                self.redirect('/select_interest')

class PursueInterestHandler(Handler):
	def get(self):
		vari = self.request.cookies.get('user_id')
		temp = checkHash(vari)
		if temp:
			name1= self.request.get('name1')
			name2 = self.request.get('name2')
			self.render('pursue_interest.html', name1=name1, name2=name2)
		#else:
		#	self.redirect('/signup')

	def post(self):
		name1 = self.request.get('name1')
		class1 = self.request.get('classes1')
		clubs1 = self.request.get('clubs1')
		comp1 = self.request.get('competitions1')
		name2 = self.request.get('name2')
		class2 = self.request.get('classes2')
		clubs2 = self.request.get('clubs2')
		comp2 = self.request.get('competitions2')
		
		first = Interest(name=name1, classes=class1, clubs=clubs1, competitions=comp1)
		second = Interest(name=name2, classes=class2, clubs=clubs2, competitions=comp2)
		first.put()
		second.put()
		vari = self.request.cookies.get('user_id')
		temp = checkHash(vari)
		if temp:
			logging.info('idNum = %s' % temp)
			user = User.get_by_key_name(temp)
			user.interest_list.append(first.key())
			user.interest_list.append(second.key())
			user.put()
			self.redirect('/newHome')

class NewHomeHandler(Handler):
	def render_page(self, user):
		#posts will be a compilation of all the user's interests
		#user can be gathered from the cookie!
		aList = user.interest_list  #returns keys of interest entities
		m = []
		posts = []
		for a in aList:
			s = Interest.get_by_id(a.id()) #gets the interest entity from the id
			m.append(s.name)
			#gets all the posts that are associated with one of the interests
			#of the user, interests are s.name
			w = Post.gql("where interest = :c", c = s.name)
			for e in w:
				posts.append(e)
				logging.info(e.title)
		self.render('new_home.html', user=user, posts=posts, intList=m)

	def get(self):
		vari = self.request.cookies.get('user_id')
		if vari == 0:
			self.redirect('/signup')
		temp = checkHash(vari)
		if temp:
			user = User.get_by_key_name(temp)
			self.render_page(user)
		else:
			self.redirect('/signup')

	def post(self):
		vari = self.request.cookies.get('user_id')
		if vari == 0:
			self.redirect('/signup')
		temp = checkHash(vari)
		if temp:
			user = User.get_by_key_name(temp)
		content=self.request.get("content")
		interest=self.request.get("interest")
		clubb = False
		title = "%s added to %s" % (user.name, interest)
		picUrl = getPic(interest)
		#picUrl = ''
		logging.info("picture url = %s" % picUrl)
		inputter = vari
		if picUrl != 'Empty':
			p = Post(picUrl = picUrl, title=title, content=content, interest=interest, inputter=inputter, club=clubb)
		else:
			p = Post(title=title, content=content, interest=interest, inputter=inputter, club=clubb)
		
		p.put()
		self.render_page(user)

class HomeHandler(Handler):
	def get(self):
		vari = self.request.cookies.get('user_id')
		temp = checkHash(vari)
		if temp:
			user = User.get_by_id(int(temp))
			aList = user.interest_list  #returns keys of interest entities
			m = {}
			for a in aList:
				s = Interest.get_by_id(a.id()) #gets the interest entity from the id
				x = Interest.gql("where name = :n", n = s.name) #gets all interest entities that have same name
				m[s.name] = {'classes': [], 'clubs': [], 'competitions': [], 'picUrl': ''}
				for ent in x:
					if ent.classes is not None:
						m[s.name]['classes'].append(ent.classes)
					if ent.clubs is not None:
						m[s.name]['clubs'].append(ent.clubs)
					if ent.competitions is not None:
						m[s.name]['competitions'].append(ent.competitions)
					if ent.picUrl is not None:
						m[s.name]['picUrl'] = ent.picUrl
					m[s.name]

			self.render('home.html', name = user.name, m = m)

	def post(self):
		pass

class SignInHandler(Handler):
    def get(self):
        self.render('signin.html')
        
    def post(self):
        username= self.request.get('username')
        password = self.request.get('password')
        hashed = hashPass(password)
        
        x = User.gql("where username = :u", u=username )
        if x.count() < 1:
        	self.render('signin.html', err1="Account information not valid")

        for a in x:
        	if a is not None and a.password == hashed:
        		logging.info("user's name is %s" % a.name)
        		logging.info("idNum = %s" % a.key().id_or_name())
        		self.setCookie(str(a.key().id_or_name()))
        		self.redirect('/newHome')
        	else:
        		self.render('signin.html', err1="Account information not valid")

class ClubSignUpHandler(Handler):
	def get(self):
		topics()
		global topic_list
		self.render('clubSignUp.html', topic_list = topic_list)

	def post(self):
		name = self.request.get('name')
		password= self.request.get('password')
		interests = self.request.get_all('interests')
		officers = self.request.get_all('officers')
		picUrl = self.request.get('picUrl')
		password = hashPass(password)
		a = Club (name=name, password=password, interests=interests, officers=officers, picUrl=picUrl)
		a.password = hashPass(password)
		a.put()

		self.response.write("Thanks for creating %s club! Your account has been activated." %a.name)
		self.response.write("Please sign in with your personal account to start adding posts.")
		#self.setCookie(str(a.key().id())) 
		#self.redirect('/clubHome/%s' % str(a.key().id()))

class ClubHomeHandler(Handler):
	def checkOfficers(self, club):
		#this method will see if cookie passed in is of one of the officers
		#if the cookie matches the list of ids in the club's officer list
		#it will set a boolean to true, if this boolean is true it will 
		#display the new post part of the form, if not it won't
		vari = self.request.cookies.get('user_id').split('|')[0]
		#temp = checkHash(vari)
		#if temp:
		#not checking the hash for now!!!!!
		if vari in club.officers:
			return True

	def render_page(self, post_id):
		topics()
		global topic_list
		club = Club.get_by_id(int(post_id))
		isOfficer = self.checkOfficers(club)
		posts = Post.gql("where inputter = :c", c = post_id)
		#I need to add the query to get the posts that will be displayed below create post
		#posts = []
		self.render('club_home.html', club=club, isOfficer=isOfficer, topic_list=topic_list, posts=posts)

	def get(self, post_id):
		self.render_page(post_id)

	def post(self, post_id):
		logging.info('POST ID = %s' % post_id)
		club = Club.get_by_id(int(post_id))
		content=self.request.get("content")
		interest=self.request.get("interest")
		clubb = True
		title = "%s added to %s" % (club.name, interest)
		picUrl = getPic(interest)
		#picUrl = ''
		logging.info("picture url = %s" % picUrl)
		#inputter is the idNum of the person writing the post
		#this will be accessed from cookie, I don't need to check it 
		inputter = post_id
		#creating this in ClubHomeHandler so club is true
		p = Post(picUrl = picUrl, title=title, content=content, interest=interest, inputter=inputter, club=clubb)
		p.put()
		self.render_page(post_id=post_id)

class LogoutHandler (Handler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        var = ''
        self.response.headers.add_header('set-cookie', 'user_id=%s;Path=/' % var)
        self.redirect('/signup')

    def post(self):
        pass

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/select_interest', SelectInterestHandler),
    ('/pursue_interest', PursueInterestHandler),
    ('/signup', SignUpHandler),
    ('/signin', SignInHandler),
    ('/logout', LogoutHandler),
    ('/home', HomeHandler),
    ('/clubSignUp', ClubSignUpHandler),
    ('/clubHome/(\w+)', ClubHomeHandler),
    ('/newHome', NewHomeHandler)
], debug=True)