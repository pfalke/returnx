#!/usr/bin/env python

import webapp2

import uuid
from google.appengine.ext import ndb

class Url(ndb.Model):
	longurl  = ndb.StringProperty()
	shorturl = ndb.StringProperty()


class MainHandler(webapp2.RequestHandler):
    def get(self):
    	# form to submit new URL
    	self.response.write("""
    		<form action='""" + self.uri_for('main') + """' method="post">
				<input type="text" name="longurl">
				<input type="submit">
			</form>
    		""")

    def post(self):
    	#retrieve URL and display it
		longurl = self.request.get('longurl')
		if 'http://' not in longurl and 'https://' not in longurl:
			longurl = 'http://' + longurl

		# check if there is an entry for this url
		url = Url.query(Url.longurl == longurl).get()
		if not url:
			# generate shorturl that has never been used
			while True:
				uid = uuid.uuid4()
				shorturl = uid.hex[:3]
				if not Url.get_by_id(shorturl): break

			url = Url(id=shorturl)
			url.longurl = longurl
			url.shorturl = shorturl
			url.put()
		self.response.write(self.uri_for('shorthandler', shorturl=url.shorturl, _full=True))


class ShortHandler(webapp2.RequestHandler):
	def get(self,shorturl):
		try:
			url = Url.get_by_id(shorturl)
			self.redirect(str(url.longurl))
			return
		except:
			self.response.write('url not found')


app = webapp2.WSGIApplication([
	webapp2.Route(r'/s', handler=MainHandler, name='main'),
    webapp2.Route(r'/s/<shorturl>', handler=ShortHandler, name='shorthandler'),
], debug=True)
