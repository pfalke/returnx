from google.appengine.ext import db
from config import DEFAULT_START_OF_DAY


class Mailstore(db.Model):
    raw_msg = db.TextProperty() # deprecated - no longer used!
    text = db.TextProperty()
    html = db.TextProperty()
    from_email = db.StringProperty()
    from_name = db.StringProperty()
    email = db.StringProperty()
    subject = db.TextProperty()
    ts = db.DateTimeProperty()
    outtime = db.DateTimeProperty()
    unsent = db.BooleanProperty()
    # if user only specifies date, default startOfDay time is used and store here
    startOfDayUsed = db.IntegerProperty()
    # when a user changes his timezone, all reminders that have been created on a
    # user specified timezone are updated
    timezoneUpdatable = db.BooleanProperty(default=False)

class Userdata(db.Model):
    email = db.StringProperty()
    usedweb = db.BooleanProperty()
    usedmail = db.BooleanProperty()
    remindersInStore = db.IntegerProperty(default=0)
    remindersSent = db.IntegerProperty(default=0)
    # for example "America/Sao Paulo"
    timeZoneAsZoneInfo = db.StringProperty()
    # at what time of the day do users get reminders if they only specify the date
    startOfDay = db.IntegerProperty(default=DEFAULT_START_OF_DAY)
    