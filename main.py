import webapp2
from google.appengine.ext import webapp
from google.appengine.api import users
import urllib2
import json
import datetime
from google.appengine.ext import db
from dateutil.relativedelta import relativedelta
from time import mktime
from parsedatetime.__init__ import Calendar
import logging

#create a config.py that has your Mandrill API key as MANDRILL_KEY.
import config
import os
import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

logging.getLogger().setLevel(logging.DEBUG)


class Mailstore(db.Model):
    raw_msg = db.TextProperty()
    text = db.TextProperty()
    html = db.TextProperty()
    from_email = db.StringProperty()
    from_name = db.StringProperty()
    email = db.StringProperty()
    subject = db.TextProperty()
    ts = db.DateTimeProperty()
    outtime = db.DateTimeProperty()
    unsent = db.BooleanProperty()

class Userdata(db.Model):
    email = db.StringProperty()
    usedweb = db.BooleanProperty()
    usedmail = db.BooleanProperty()
    
def parsetime(mailstr):
    cal = Calendar()
    out = cal.parse(mailstr)
    return datetime.datetime.fromtimestamp(mktime(out[0]))

def seteightam(maildate):
    #if maildate later than tomorrow, time is set to 8am = 7am UTC
    now = datetime.datetime.today()
    if maildate >= now+relativedelta(days=1):
        maildate= datetime.datetime(maildate.year,maildate.month,maildate.day,7,0,0)
    return maildate

def sendmail(maildict):
    #sends email via Manrill, returns HTTP response from Mandrill
    mailjson = json.dumps(maildict)
    url = 'https://mandrillapp.com/api/1.0/messages/send.json'
    try:
        f = urllib2.urlopen(url, mailjson)
        response = f.read()
        f.close()
    except:
        logging.error('cannot send mail')
        response = -1
    return str(response)

def sendEmail(recipient_mail,subject,recipient_name='',text='',from_email='reminders@a.pfalke.com',from_name='Reminders',tag='automail',html=''):
    maildict = {
        "key": config.MANDRILL_KEY,
        "message": {
        "text": text,
        "subject": subject,
        "from_email": from_email,
        "from_name": from_name,
        "to": [
               {
               "email": recipient_mail,
               "name": recipient_name
               }
               ],
        "tags": [
                 tag
                 ]
    }
    }    
    if not html=='':
        maildict['message']['html'] = html
    response = sendmail(maildict)
    return response

def senderrormail(problem, err,recipient_mail='test@pfalke.com',recipient_name='Admin'):
    logging.error(problem)
    logging.error(str(err))
    return sendEmail(recipient_mail,problem+" Error "+str(err),recipient_name=recipient_name,text="Error with "+problem+": " + str(err),from_email="problems@a.pfalke.com",from_name='Reminder Trouble',tag="errormessage")


def sendusermail(email, channel):
    if email == "test@example.com": return 'no mails for this guy.'
    response = sendEmail('x@pfalke.com',subject=email + " now uses returnX "+ channel,recipient_name='Admin',text=email + " now uses returnX "+ channel,from_email="newusers@pfalke.com",from_name="returnX new users",tag='newuser')
    return response

def printquery(query,loggedin=True):
    htmlstring = '''<table>
            <thead>
            <tr>
                <th class="due">
                    Due
                </th>
                <th class="subject">
                    Subject
                </th>
                <th class="for">
                    For
                </th>
                <th class="created">
                    Created
                </th>
                <th class="delete">
                    Delete
                </th>
            </tr>
            </thead><tbody>'''
    if not loggedin or not query:
        htmlstring += '</tbody></table>'
        return htmlstring
    if query.count() == 0:
        htmlstring += '</tbody></table><p>No reminders - <a href="mailto:tomorrow@a.pfalke.com?Subject=Reminder%20from%20yesterday">create one now</a>!</p>'
    else:
        for mailer in query:
            try:
                now = datetime.datetime.now()
                htmlstring += """<tr class="reminderRow" id="%s">
                <td class="due"><span>%s</span>
                """ %(mailer.key(),str(mailer.outtime.strftime("%d %b %Y %H:%M")))
                if mailer.outtime > now:
                    htmlstring += """
                    <div class="editbutton">Edit</div>
                    <form action="/updateReminder" method="post" class="updateForm">
                        <input type="hidden" name="key" value="%s"/>
                        <input name="changedate" type="date" value="%s" min="%s" class="dateinput"/>
                        <input name="changetime" type="time" value="%s" class="timeinput"/>
                        <div class="submitbutton">Change</div>
                    </form>""" %(mailer.key(),
                      mailer.outtime.strftime('%Y-%m-%d'),
                      now.strftime('%Y-%m-%d'),
                      mailer.outtime.strftime('%H:%M'))
                htmlstring += """
                </td>
                <td class="subject">%s</td>
                <td>%s<br>%s</td>
                <td>%s<br>%s</td>
                <td><div class='deletebutton' key='%s'>Delete</div>
                </tr>
                """ % (mailer.subject,
                      mailer.from_name,
                      mailer.from_email,
                      str(mailer.ts.strftime("%d %b %Y %H:%M")),
                      mailer.email,
                      mailer.key())
            except Exception, err:
                htmlstring += '<p>Exception '+str(err)+' while trying to output mail.</p>'
        htmlstring += '</tbody></table>'
    return htmlstring 

def seenuserbefore(email, usedweb=False, usedmail=False):
    beenseenbeforequery = db.GqlQuery("SELECT * "
                                      "FROM Userdata "
                                      "WHERE email = :1 "
                                      "ORDER BY email LIMIT 10",
                                      email)
    if beenseenbeforequery.count() == 0:
        thisuser = Userdata(email=email,usedweb=usedweb,usedmail=usedmail)
        sendusermail(email,'one the web!' if usedweb else 'via mail!')
        thisuser.put()
        return thisuser
    else:
        if beenseenbeforequery.count(limit=2)>1:
            senderrormail('multiple users in DB for email ' + email, 'Error')
        thisuser = beenseenbeforequery[0]
        if usedweb and not thisuser.usedweb:
            thisuser.usedweb = True
            thisuser.put()
        if usedmail and not thisuser.usedmail:
            thisuser.usedmail = True
            thisuser.put()
        return thisuser
     
class UpdateReminder(webapp2.RequestHandler):
    def post(self):
        try:
            dateobj = datetime.datetime.strptime(self.request.get('changedate')+'-'+self.request.get('changetime'),'%Y-%m-%d-%H:%M')
            key = self.request.get('key', default_value='', allow_multiple=False)
            user = users.get_current_user()
            mailer = db.get(key)
            if users.is_current_user_admin() or mailer.parent().email.lower() == user.email().lower():
                mailer.outtime = datetime.datetime(dateobj.year, dateobj.month, dateobj.day,dateobj.hour,dateobj.minute,mailer.outtime.second)
                mailer.put()
                self.response.out.write(str(mailer.outtime.strftime("%d %b %Y %H:%M")))
                return
            else:
                senderrormail('Illegal update attempt', 'Error')
                self.response.out.write("Keep your fingers off!")
                return
        except Exception, err:
            senderrormail('Trying to update reminder: ',err)
            self.response.out.write("Please refresh.")
            return

class Sendmail(webapp2.RequestHandler):
    #reads unsent mails of the last hour from datastore, creates json for mandrill, sends mail
    def get(self):
        self.response.out.write('''<html><body>''')
        now = datetime.datetime.now()
        self.response.out.write('<p>It is now '+now.ctime()+'.</p>')
        mailers = db.GqlQuery("SELECT * "
                              "FROM Mailstore "
                              "WHERE outtime <= :1 AND unsent = True "
                              "ORDER BY outtime DESC LIMIT 10",
                              now)
        for mailer in mailers:
            subject = "Reminder" if mailer.subject == None or mailer.subject == "" else mailer.subject
            try:
                response = sendEmail(mailer.from_email,
                                     subject,
                                     recipient_name=mailer.from_name,
                                     text=mailer.text,
                                     from_email='reminders@a.pfalke.com',
                                     from_name="Reminder via "+mailer.email,
                                     tag='Reminder',
                                     html=mailer.html)
                if response == -1:
                    senderrormail("Couldn't send reminder", "Mandrill")
                else:
                    mailer.unsent = False
                    mailer.put()
                    self.response.out.write('<p>Mail sent to '+mailer.from_name+' ('+mailer.from_email+') who had written at '+mailer.ts.ctime()+' and whose reminder was due '+mailer.outtime.ctime()+'. Status Code: '+response+'</p>')
            except Exception, err:
                self.response.out.write('<p>Encountered exception '+str(err)+' when trying to send mail to '+mailer.from_name+' ('+mailer.from_email+').</p>')
        self.response.out.write('''
                    </body>
                    </html>
                    ''')

class MyRequestHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            seenuserbefore(user.email().lower(),usedweb=True)
            logout = '<p align="right">%s (%s), <a href=\"%s\">log out</a></p>' % (user.nickname(), user.email() ,users.create_logout_url("/"))
        else:
            logout = '<p align="right"><a href=\"%s\">log in</a></p>' % (users.create_login_url(self.request.uri))
        self.response.out.write('''
            <!DOCTYPE html PUBLIC "-//IETF//DTD HTML 2.0//EN">
            <HTML>
            <head>
            <script src="http://code.jquery.com/jquery-latest.min.js" type="text/javascript"></script>
            <script type='text/javascript' src='/stylesheets/script.js'></script>
            <style media="screen" type="text/css">
            html, body {height: 100%;}
            
            #wrap {min-height: 100%;}
            
            #main {overflow:auto;
            padding-bottom: 50px;}  /* must be same height as the footer */
            
            #footer {position: relative;
            margin-top: -50px; /* negative value of footer height */
            height: 50px;
            clear:both;}
            </style>
            <link rel="stylesheet" href="/stylesheets/style.css" />
            <TITLE>
            returnX
            </TITLE>
            <script>
              (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
              (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
              m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
              })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

              ga('create', 'UA-43315489-1', 'pfalke.com');
              ga('send', 'pageview');

            </script>
            </head>
            <body><div id="wrap">
            <div id="main">''')
        # Make form for update AJAX
            # <script src="http://malsup.github.com/jquery.form.js"></script> 
            # <script> 
            #     $(document).ready(function() { 
            #         // bind 'updateForm' and provide a simple callback function 
            #         $('.updateForm').ajaxForm(function() { 
            #             alert("Thank you for your comment!"); 
            #         }); 
            #     }); 
            # </script> 
            
        self.response.out.write('''%s
            <H1>Hi there%s</H1>''' % (logout,("" if not user else ", "+user.nickname())))
        if users.is_current_user_admin():
            self.response.out.write('<p><a href=%s>Queue</a> - <a href="https://appengine.google.com/dashboard?&app_id=s~returnitx">Dashboard</a></p>' % (self.uri_for('queue',_full=True)))
        #Begruessung
        self.response.out.write('''
            <p>This is an email reminder service. Want to be reminded about something in 5 days and not hear about it till then? Just send an email to 5days@a.pfalke.com and your reminder comes in 5 days! Any type of time works: monday@a.pfalke.com, june23@a.pfalke.com, ...<p>
            <p>Note that this app was merely created for trying a few things out. It may be neither reliable nor secure. Don't use it for sensitive/critical things!</p>
            <h1>Your Reminders</h1>
            ''')
        if user:
            now = datetime.datetime.now()
            mailers = db.GqlQuery("SELECT * "
                                  "FROM Mailstore "
                                  "WHERE outtime <= :1 AND unsent = True AND from_email = :2 " 
                                  "ORDER BY outtime DESC LIMIT 100",
                                  now, user.email().lower())
            duenow = mailers.count()
            if duenow>0:
                self.response.out.write('<h3>Due now: '+str(duenow)+' %s</h3>' % ('reminders' if duenow>1 else 'reminder'))
                self.response.out.write('Will be send within the next minute.')
                self.response.out.write(printquery(mailers))
            mailerqueue = db.GqlQuery("SELECT * "
                                      "FROM Mailstore "
                                      "WHERE outtime >= :1 AND unsent = True AND from_email = :2 "
                                      "ORDER BY outtime LIMIT 100",
                                      datetime.datetime.now(), user.email().lower())
            self.response.out.write('<h3>Queue</h3>')
            self.response.out.write(printquery(mailerqueue))
            pastreminders = db.GqlQuery("SELECT * "
                                      "FROM Mailstore "
                                      "WHERE outtime <= :1 AND unsent = False AND from_email = :2 "
                                      "ORDER BY outtime DESC LIMIT 100",
                                      datetime.datetime.now(), user.email().lower())
            numberpastrem = pastreminders.count()
            if numberpastrem >0:
                if numberpastrem <100:
                    self.response.out.write('<h3>You have received '+str(numberpastrem)+' %s so far.</h3>' % ('reminders' if numberpastrem>1 else 'reminder'))
                else:
                    self.response.out.write('<h3>Your last 100 reminders.</h3>')
                self.response.out.write(printquery(pastreminders))
        else:
            self.response.out.write(printquery(None,loggedin=False))
            self.response.out.write("<p><a href=\"%s\">Log in</a> to see your reminders - no signup required! Gmail users only.</p>" %users.create_login_url(self.request.uri))
        self.response.out.write('''     </div> </div><div id="footer">Philipp - contact me via x at pfalke.com. Written using Google App Engine, Mandrill, <a href="https://github.com/bear/parsedatetime">parsedatetime</a> and <a href="http://labix.org/python-dateutil">dateutil</a>. </div></body></HTML>''')


class DeleteReminderHandler(webapp2.RequestHandler):
    def post(self):
        try:
            if 'key' in self.request.arguments():
                key = self.request.get('key', default_value='', allow_multiple=False)
                user = users.get_current_user()
                mailer = db.get(key)
                if users.is_current_user_admin() or mailer.parent().email.lower() == user.email().lower():
                    mailer.delete()
                    self.response.out.write('Success')
                    return
                else:
                    senderrormail('Illegal delete attempt', 'Error')
        except Exception, err:
            senderrormail('Trying to delete reminder: ',err)
        self.response.out.write('Fail')
        return
        
#Receives Mandrill Webhooks for incoming mail
class InboundRequestHandler(webapp.RequestHandler):
    logging.getLogger().setLevel(logging.DEBUG)
    #incoming Mandrill Webhook
    def post(self):
        try:
            #extract data from webhook
            mandrilldata = json.loads(self.request.get('mandrill_events'))
            messagedata = mandrilldata[0]['msg']
        except Exception, err:
            senderrormail("JSON load",err)
        #lookup user in datastore
        thisuser = seenuserbefore(messagedata['from_email'].lower(),usedmail=True)
        try:
            #create reminder in datastore
            mailer = Mailstore(parent=thisuser, 
                               unsent=True, 
                               ts=datetime.datetime.now(),
                               from_email = messagedata['from_email'].lower(),
                               email = messagedata['email'])
        except Exception, err:
            senderrormail("Read from",err)
            return
        #store more data from request
        mailer.raw_msg = messagedata['raw_msg'] if 'raw_msg' in messagedata else ''
        mailer.subject = messagedata['subject'] if 'subject' in messagedata else 'Reminder'
        mailer.text = messagedata['text'] if 'text' in messagedata else mailer.subject
        mailer.html = messagedata['html'] if 'html' in messagedata else ''
        mailer.from_name = messagedata['from_name'] if 'from_name' in messagedata else ''
        #parse timedelta from email
        mailsendtime = None
        try:
            mailsendtime = parsetime(mailer.email)
            mailer.outtime = seteightam(mailsendtime)
        except Exception, err:
            senderrormail("Timing your reminder",err)
            return
        try:
            #check if time was successfully parsed
            if mailer.outtime <= datetime.datetime.now()+relativedelta(minutes=10):
                sendEmail(recipient_mail=mailer.from_email,
                          subject="Couldn't recognize time for your reminder!",
                          text="Couldn't recognize time for your reminder!",
                          from_email="reminders@a.pfalke.com",
                          tag="time parse error message")
            else:
                #store reminder
                mailer.put()
        except Exception, err:
            senderrormail("Check if time valid/send error mail",err)

    def head(self):
        pass

#Displays the queue to admins

class QueueRequestHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('''<html><head>
        <link rel="stylesheet" href="/stylesheets/style.css" />
        <script src="http://code.jquery.com/jquery-latest.min.js"  type="text/javascript"></script>
        </head><body>''')
        now = datetime.datetime.now()
        self.response.out.write('<p><a href=%s>Home</a> - It is now %s.</p>' % (self.uri_for('mainpage',_full=True),now.ctime()))
        user = users.get_current_user()
        if user:
            self.response.out.write('<p align="right">%s (%s), <a href=\"%s\">log out</a></p>' % (user.nickname(), user.email() ,users.create_logout_url("/")))
            if users.is_current_user_admin():
                totalmailers = db.GqlQuery("SELECT * "
                                      "FROM Mailstore ")
                #self.response.out.write('Numer of Mails due now: '+str(mailers.count())+'<br>')
                self.response.out.write('<p>Total Reminders: %s.</p>' %totalmailers.count())
                self.response.out.write('<h3>Due now</h3>')
                mailers = db.GqlQuery("SELECT * "
                                      "FROM Mailstore "
                                      "WHERE outtime <= :1 AND unsent = True "
                                      "ORDER BY outtime LIMIT 10",
                                      now)
                #self.response.out.write('Numer of Mails due now: '+str(mailers.count())+'<br>')
                if mailers.count() > 0:
                    self.response.out.write(printquery(mailers))
                else:
                    self.response.out.write("<p>No reminders due now.</p>")
                self.response.out.write('<h3>Remaining Queue</h3>')
                mailerqueue = db.GqlQuery("SELECT * "
                                          "FROM Mailstore "
                                          "WHERE outtime >= :1 AND unsent = True "
                                          "ORDER BY outtime LIMIT 1000",
                                          datetime.datetime.now())
                if mailerqueue.count() > 0:
                    self.response.out.write(printquery(mailerqueue))
                else:
                    self.response.out.write("<p>No reminders in queue.</p>")
                self.response.out.write('<h3>Last 100 reminders.</h3>')
                pastreminders = db.GqlQuery("SELECT * "
                                            "FROM Mailstore "
                                            "WHERE outtime <= :1 AND unsent = False "
                                            "ORDER BY outtime DESC LIMIT 100",
                                            datetime.datetime.now())
                if pastreminders.count() > 0:
                    self.response.out.write(printquery(pastreminders))
                else:
                    self.response.out.write("<p>No past reminders.</p>")
                self.response.out.write('''
                        </body>
                        </html>
                        ''')
            else:
                self.redirect(users.create_login_url(self.request.uri))

app = webapp2.WSGIApplication([
       webapp2.Route(r'/', handler=MyRequestHandler, name='mainpage'),
       webapp2.Route(r'/updateReminder', handler=UpdateReminder, name='updateReminder'),
       ('/inbound', InboundRequestHandler),
       webapp2.Route(r'/queue', handler=QueueRequestHandler, name='queue'),
       ('/deleteReminder', DeleteReminderHandler),
       webapp2.Route(r'/sendmail/', handler=Sendmail, name='sendmail')],
       debug=True)