import webapp2
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.api import urlfetch
import urllib2
import json
import datetime
from dateutil.relativedelta import relativedelta
from parseTime import parseTime
import logging

# create a config.py that has your Mandrill API key as MANDRILL_KEY.
import config
import os
import jinja2

import re
from dateutil.tz import *
from dateutil import zoneinfo
import timezones

from models import *


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

logging.getLogger().setLevel(logging.DEBUG)

def sendmail(maildict):
    #sends email via Manrill, returns HTTP response from Mandrill
    mailjson = json.dumps(maildict)
    try:
        result = urlfetch.fetch(
            url=config.AWS_SENDMAIL_API_RESOURCE,
            payload=mailjson,
            method=urlfetch.POST,
            headers={"Content-Type":"application/json"}
            )
        response = result['content']
    except Exception, err:
        logging.error(str(err))
        response = -1
    return str(response)

def sendEmail(
    recipient_mail,
    subject,
    recipient_name='',
    text='',
    from_email=config.REMINDER_FROM_ADDRESS,
    from_name='Reminders',
    tag='automail',html=''):
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

def sendErrorMailToAdmin(problem,
    exception,
    details='none',
    recipient_mail=config.ADMIN_MAIL_ADDRESS,
    recipient_name='Admin'):
    logging.error('Problem: ' + problem)
    logging.error('Exception: ' + str(exception))
    logging.error('Details: %s' % details)
    return sendEmail(
        recipient_mail,
        problem+" Error "+str(exception),
        recipient_name=recipient_name,
        text="Error with " + problem + ".\n Exception: " + str(exception) +'\nDetails: ' + details,
        from_email=config.ERROR_FROM_ADDRES,
        from_name='Reminder Trouble',
        tag="errormessage")

def sendErrorMailToUser(recipient_mail, text='''Something went wrong when creating your reminder.
                It might help to try again later. Also, attachments are known to mess things up.
                \nThat's all we know. Sorry!'''):
    sendEmail(recipient_mail=recipient_mail,
              subject="Couldn't create your reminder!",
              text=text,
              from_email=config.ERROR_FROM_ADDRES,
              tag="time parse error message")
    logging.warning("Sent error mail to user %s because of error:\n %s" % (recipient_mail, text))


def sendusermail(email, channel):
    if email == "test@example.com": return 'no mails for this guy.'
    response = sendEmail(
        config.ADMIN_MAIL_ADDRESS,
        subject="%s now uses %s %s" %(email,os.environ['APPLICATION_ID'],channel),
        recipient_name='Admin',
        text="%s now uses %s %s" %(email,os.environ['APPLICATION_ID'],channel),
        from_email=config.NEW_USER_FROM_ADRESS,
        from_name=os.environ['APPLICATION_ID'] + " new users",
        tag='newuser')
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
        htmlstring += '''
            </tbody></table><p>
            No reminders - <a href="mailto:%s?Subject=%s">
            create one now</a>!</p>''' % (config.SAMPLE_REMINDER_ADDRESS,'ReminderFromYesterday')
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
            sendErrorMailToAdmin('multiple users in DB for email ' + email, 'Error')
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
                sendErrorMailToAdmin('Illegal update attempt', 'Error')
                self.response.out.write("Keep your fingers off!")
                return
        except Exception, err:
            sendErrorMailToAdmin('Trying to update reminder: ',err)
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
                                     from_email=config.REMINDER_FROM_ADDRESS,
                                     from_name="Reminder via "+mailer.email,
                                     tag='Reminder',
                                     html=mailer.html)
                if response == -1:
                    sendErrorMailToAdmin("Couldn't send reminder", "Mandrill")
                else:
                    mailer.unsent = False
                    mailer.put()
                    self.response.out.write('<p>Mail sent to '+mailer.from_name+' ('+mailer.from_email+') who had written at '+mailer.ts.ctime()+' and whose reminder was due '+mailer.outtime.ctime()+'. Status Code: '+response+'</p>')
            except Exception, err:
                self.response.out.write('<p>Encountered exception '+str(err)+' when trying to send mail to '+mailer.from_name+' ('+mailer.from_email+').</p>')
            try:
                reminderCreator = mailer.parent()
                if reminderCreator:
                    if reminderCreator.remindersInStore:
                        reminderCreator.remindersInStore -=1
                    if not reminderCreator.remindersSent:
                        reminderCreator.remindersSent = 0
                    reminderCreator.remindersSent +=1
                    reminderCreator.put()
            except Exception, e:
                logging.error('Could not update reminder count: %s' % e)


        self.response.out.write('''
                    </body>
                    </html>
                    ''')

class MyRequestHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        template_values = {
            'loggedIn': False
        }

        # Login/logout stuff
        if user:
            seenuserbefore(user.email().lower(),usedweb=True)
            template_values['loggedIn'] = True
            template_values['userData'] = {
                'nickname': user.nickname(),
                'email': user.email(),
                'logOutUrl': users.create_logout_url("/")
            }
        else:
            template_values['logInUrl'] = users.create_login_url(self.request.uri)

        if users.is_current_user_admin():
            template_values['queueURI'] = self.uri_for('queue',_full=True)

        # table of reminders
        if user:
            now = datetime.datetime.now()
            mailers = db.GqlQuery("SELECT * "
                                  "FROM Mailstore "
                                  "WHERE outtime <= :1 AND unsent = True AND from_email = :2 " 
                                  "ORDER BY outtime DESC LIMIT 100",
                                  now, user.email().lower())
            duenow = mailers.count()
            if duenow>0:
                template_values['duenow'] = duenow
                template_values['dueMailers'] = printquery(mailers)
            mailerqueue = db.GqlQuery("SELECT * "
                                      "FROM Mailstore "
                                      "WHERE outtime >= :1 AND unsent = True AND from_email = :2 "
                                      "ORDER BY outtime LIMIT 100",
                                      datetime.datetime.now(), user.email().lower())
            template_values['mailerqueue'] = printquery(mailerqueue)

            pastreminders = db.GqlQuery("SELECT * "
                                      "FROM Mailstore "
                                      "WHERE outtime <= :1 AND unsent = False AND from_email = :2 "
                                      "ORDER BY outtime DESC LIMIT 100",
                                      datetime.datetime.now(), user.email().lower())
            numberpastrem = pastreminders.count()
            if numberpastrem >0:
                template_values['pastreminders'] = printquery(pastreminders)
        else: # show sample reminders
            template_values['sampleReminders'] = printquery(None,loggedin=False)

        # render the template
        template = JINJA_ENVIRONMENT.get_template('mainPage.html')
        self.response.write(template.render(template_values))


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
                    sendErrorMailToAdmin('Illegal delete attempt', 'Error')
        except Exception, err:
            sendErrorMailToAdmin('Trying to delete reminder: ',err)
        self.response.out.write('Fail')
        return

# return test from test@example.com, does not check if the string is a valid email address
def stringBeforeAtSign(emailAdress):
    matchObj = re.match(r'([^@]+)@', emailAdress)
    if matchObj:
        return matchObj.group(1)
    return None
        
def inferTimezoneFromHeader(headerString):
    tzRegex = r'''
        (?P<sign>[-+])
        (?P<amount>\d{4})
        '''
    matches = re.search(tzRegex, headerString, re.VERBOSE)
    if not matches:
        raise Exception('no match')
    sign, amount = matches.group('sign', 'amount')
    utcOffset = 3600 * (-1 if sign == '-' else 1) * int(amount)/100
    return tzoffset("inferredFromHeader %s%s" % (sign,amount), utcOffset)

def getTimezone(userObject,messagedata):
    # if user has specified timezone, try both functions to get TZ object
    if userObject.timeZoneAsZoneInfo:
        try:
            tz = zoneinfo.gettz(userObject.timeZoneAsZoneInfo)
            if tz:
                logging.info('using user-specified timezone %s (%s) from zoneinfo' \
                    % (userObject.timeZoneAsZoneInfo, tz))
                return (tz, True)
        except Exception, e:
            logging.info('using zoneinfo func failed: %s' % e)
        try:
            tz = gettz(userObject.timeZoneAsZoneInfo)
            if tz:
                logging.info('using user-specified timezone %s (%s) from gettz' \
                    % (userObject.timeZoneAsZoneInfo, tz))
                return (tz, True)
        except Exception, e:
            logging.info('using gettz func failed: %s' % e)

    # extract UTC offset from email header and use it
    try:
        tz = inferTimezoneFromHeader(messagedata['headers']['Date'])
        logging.info('timezone inferred: %s' % tz)
    except Exception, e:
        logging.info('timezone not recognized: %s' % e)
        tz = tzoffset("defaultUtcOffsett", config.DEFAULT_UTC_OFFSETT * 3600)
    return (tz, False)


#Receives Mandrill Webhooks for incoming mail
class InboundRequestHandler(webapp.RequestHandler):
    logging.getLogger().setLevel(logging.DEBUG)
    #incoming Mandrill Webhook
    def post(self):
        try:
            # extract data from webhook
            logging.info('length of recieved JSON: %s' % len(self.request.get('mandrill_events')))
            mandrilldata = json.loads(self.request.get('mandrill_events'))
            messagedata = mandrilldata[0]['msg']
            logging.info('successfully decoded JSON')
            if not mandrilldata[0]['key'] == config.MANDRILL_KEY:
                logging.error('Inbound email request with non-matching secret key. Received key: %s' % mandrilldata[0]['key'])
        except Exception, err:
            sendErrorMailToAdmin(
                "Exception loading JSON.", err,
                details='''
Could not load JSON for mail from %s to %s''' % (mailer.from_email,
                    mailer.email))
            sendErrorMailToUser(mailer.from_email)
        # lookup user in datastore
        thisuser = seenuserbefore(messagedata['from_email'].lower(),usedmail=True)
        # Timezone to be used with the reminder
        timezoneObject, tzSpecifiedByUser = getTimezone(thisuser, messagedata)
        try:
            #create reminder in datastore
            mailer = Mailstore(parent=thisuser, 
                               unsent=True, 
                               ts=datetime.datetime.now(),
                               from_email = messagedata['from_email'].lower(),
                               email = messagedata['email'])
        except Exception, err:
            sendErrorMailToAdmin(
                "Exception creating datastore object.", err,
                details='''
Could not create datastore object for mail from %s to %s''' % (mailer.from_email,
                    mailer.email))
            sendErrorMailToUser(mailer.from_email)
            return
        #store more data from request
        mailer.subject = messagedata['subject'] if 'subject' in messagedata else 'Reminder'
        mailer.text = messagedata['text'] if 'text' in messagedata else mailer.subject
        mailer.html = messagedata['html'] if 'html' in messagedata else ''
        mailer.from_name = messagedata['from_name'] if 'from_name' in messagedata else ''
        #parse timedelta from email
        try:
            timestring = stringBeforeAtSign(mailer.email)
            mailer.outtime, startOfDayUsed = parseTime(timestring, timezoneObject, thisuser.startOfDay)
            #check if time was successfully parsed
            if not mailer.outtime or \
                mailer.outtime <= datetime.datetime.now(timezoneObject)+relativedelta(minutes=5):
                sendErrorMailToUser(
                    mailer.from_email,
                    text="Couldn't recognize time \"%s\" for your reminder!" % mailer.email)
                return 
            #store reminder
            mailer.startOfDayUsed = startOfDayUsed
            mailer.timezoneUpdatable = tzSpecifiedByUser
            mailer.put()
        except Exception, err:
            sendErrorMailToAdmin(
                "Exception timing/storing a reminder.", err,
                details='Could not time/store reminder for mail from %s to %s' % (mailer.from_email,
                    mailer.email))
            sendErrorMailToUser(mailer.from_email)
            logging.error('html: \n%s' % mailer.html)
            logging.error('text: \n%s' % mailer.text)
            return
        try:
            if not thisuser.remindersInStore:
                thisuser.remindersInStore = 0
            thisuser.remindersInStore +=1
            thisuser.put()
        except Exception, e:
            logging.error('Could not update reminder count: %s' % e)

    # Mandrill sends HEAD request to check if webhook URL is valid
    def head(self):
        pass

#Displays the queue to admins
class QueueRequestHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('''<html><head>
        <link rel="stylesheet" href="/staticAssets/style.css" />
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


def _12hTimeTo24hTime(timestring):
    if timestring == '12am':
        # midnight
        return 0
    if timestring == '12pm':
        # noon
        return 12
    matchObj = re.match(r'(?P<number>\d{1,2})(?P<amPm>am|pm)', timestring)
    if not matchObj:
        raise Exception('could not extract time')
    (number, amPm) = matchObj.group('number', 'amPm')
    number = int(number)
    if amPm == 'pm':
        number += 12
    return number

def _24hTimeTo12hTime(timeNumber):
    if timeNumber == 0:
        return '12am'
    if timeNumber == 12:
        return '12pm'
    if timeNumber < 12:
        return str(timeNumber) + 'am' 
    return str(timeNumber-12) + 'pm'


class SettingsHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        template_values = {
            'loggedIn': False,
            'domain': config.DOMAIN,
            'GA_code': config.GOOGLE_ANALYTICS_ID
        }

        template_values['userData'] = {
            'nickname': user.nickname(),
            'email': user.email(),
            'logOutUrl': users.create_logout_url("/")
        }

        userObject = seenuserbefore(user.email().lower(), usedweb=True, usedmail=False)

        template_values['formUri'] = self.uri_for('settings')

        template_values['userSettings'] = {
            'startOfDay': _24hTimeTo12hTime(userObject.startOfDay),
            'timeZoneAsZoneInfo': userObject.timeZoneAsZoneInfo
        }

        template_values['timezones'] = timezones.GOOD_ZONES

        # render the template
        template = JINJA_ENVIRONMENT.get_template('userSettings.html')
        self.response.write(template.render(template_values))

    def post(self):
        user = users.get_current_user()
        userObject = seenuserbefore(user.email().lower(), usedweb=True, usedmail=False)
        logging.info(self.request.get('startOfDay'))
        logging.info(self.request.get('zoneInfo'))
        startOfDay = _12hTimeTo24hTime(self.request.get('startOfDay'))
        logging.info(startOfDay)
        userObject.startOfDay = startOfDay
        # FIRST CHECK IF THIS TIMEZONE WORKS!
        userObject.timeZoneAsZoneInfo = self.request.get('zoneInfo')
        userObject.put()
        self.redirect(self.uri_for('settings'))


# checks if a given timezone is installed
def tryTz(timeZoneAsZoneInfo):
    tz = gettz(timeZoneAsZoneInfo)
    if tz:
        # logging.info(tz)
        return 'gettz'
    tz = zoneinfo.gettz(timeZoneAsZoneInfo)
    if tz:
        # logging.warning(tz)
        return 'zoneinfo'
    return False


# timezones are hardcoded in the timezones.py file. In case the zones installed on the
# server change, this handler called daily by a cron job to check if all selectable zones are
# still present
class CheckTimezonesHandler(webapp.RequestHandler):
    def get(self):
        try:
            goodZones = []
            badZones = []
            usedZoneinfo = False
            usedGettz = False
            for i in timezones.GOOD_ZONES:
            # for i in ['Africa/Abidjan', 'Africa/Accra', r'Africa/Addis Ababa']:
                x = tryTz(i)
                if not x:
                    badZones.append(i)
                    logging.warning(i)
                else:
                    goodZones.append(i)
                if x == 'gettz':
                    usedGettz = True
                elif x == 'zoneinfo':
                    usedZoneinfo = True
        except Exception, e:
            sendErrorMailToAdmin('timezones', e)
        # we have implemented two functions for instantiating a timezoneObject from a
        # zoneinfo string. display which ones are actually used
        logging.info('used gettz: %s' % usedGettz)
        logging.info('used zoneinfo: %s' % usedZoneinfo)
        logging.info(goodZones)
        logging.info(badZones)
        # if len(badZones)>0:
        #     sendErrorMailToAdmin('timezones','',str(badZones))
        self.response.out.write(str(len(goodZones)) + ' ' + str(len(badZones)))


class TestHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write(_parseDaytime('1pm'))


app = webapp2.WSGIApplication([
       webapp2.Route(r'/test', handler=TestHandler, name='test'),
       webapp2.Route(r'/settings', handler=SettingsHandler, name='settings'),
       webapp2.Route(r'/', handler=MyRequestHandler, name='mainpage'),
       webapp2.Route(r'/updateReminder', handler=UpdateReminder, name='updateReminder'),
       ('/inbound', InboundRequestHandler),
       webapp2.Route(r'/queue', handler=QueueRequestHandler, name='queue'),
       ('/deleteReminder', DeleteReminderHandler),
       webapp2.Route(r'/sendmail', handler=Sendmail, name='sendmail'),
       webapp2.Route(r'/checkTimezones', handler=CheckTimezonesHandler, name='checkTimezones')
       ],
       debug=True)