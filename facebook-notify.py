#!/usr/bin/env python
#Facebook Notify - Facebook status notifier for GNOME
#Copyright (C) 2009 John Stowers <john.stowers@gmail.com>
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gobject
import gtk
import pynotify
import webkit
import facebook

import time
import threading
import tempfile
import urllib2
import os.path

class SimpleBrowser(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self._sw = gtk.ScrolledWindow()
        self._bv = webkit.WebView()
        self._sw.add(self._bv)
        self.add(self._sw)

    def _move_window_to_status_icon(self, si):
        screen, pos, orientation = si.get_geometry()
        #window.set_gravity(gtk.gdk.GRAVITY_SOUTH_EAST)
        #width, height = window.get_size()
        #window.move(gtk.gdk.screen_width() - width, gtk.gdk.screen_height() - height)


    def open_url(self, url, statusicon=None):
        if statusicon and statusicon.is_embedded():
            self._move_window_to_status_icon(statusicon)
        else:
            self.set_position(gtk.WIN_POS_CENTER)
        self.set_size_request(800,600)
        self._bv.open(url)
        self.show_all()
        

class FacebookCommunicationManager(threading.Thread):

    FB_AID = 44911717818
    FB_API_KEY = "cf61e1494a431f7db3c8372cc4a17bdf"
    FB_SECRET = "144b35ddb210ca2543051d4a3d03313b"

    def __init__(self):
        threading.Thread.__init__(self)
        #func : (cb, *args, **kwargs)
        self._pending = []
        self._pending_photos = []
        self._photo_cache = {}
        self._stopped = False
        self._event = threading.Event()
        self._fb = facebook.Facebook(self.FB_API_KEY, self.FB_SECRET)
        self._tmpdir = tempfile.mkdtemp(prefix="facebook",suffix="cache")

    def stop(self):
        self._stopped = True
        #self._event.set()

    def call_facebook_function(self, cb, func, *args, **kwargs):
        self._pending.insert(0, (cb, func, args, kwargs))
        #self._event.set()

    def download_photo(self, cb, url, *args, **kwargs):
        if url in self._photo_cache:
            cb(self._photo_cache[url], *args, **kwargs)
        else:
            self._pending_photos.insert(0, (cb, url, args, kwargs))
            #self._event.set()

    def get_login_url(self):
        return self._fb.get_login_url()

    def run(self):
        while not self._stopped:
            while True:
                #do any pending facebook calls
                try:
                    cb, funcname, args, kwargs = self._pending.pop()
                    print "Calling %s... " % funcname,
                    func = self._fb
                    for f in funcname.split("."):
                        func = getattr(func, f)
                    try:
                        res = func(*args)
                        print "finished"
                    except facebook.FacebookError:
                        print "error"
                        res = {}
                    except urllib2.URLError:
                        print "error"
                        res = {}
                    cb(res)
                except IndexError:
                    break

                #do any pending image downloads
                try:
                    cb, url, args, kwargs = self._pending_photos.pop()
                    try:
                        print "Downloading %s... " % url
                        inf = urllib2.urlopen(url)
                        fd, pic = tempfile.mkstemp(dir=self._tmpdir,suffix=".jpg")

                        os.write(fd, inf.read())
                        os.close(fd)
                        inf.close()

                        print "finished"
                        self._photo_cache[url] = pic
                    except urllib2.URLError, e:
                        print "error: %s" % e
                        pic = ""

                    cb(pic, *args, **kwargs)
                except IndexError:
                    break

                #minimum of 1 second between subsequent facebook calls
                time.sleep(1)

            time.sleep(0.1)
            #self._event.wait()
            #self._event.clear()

class Gui:

    SECONDS_1_MIN = 60
    SECONDS_1_HOUR = 60*60
    SECONDS_1_DAY = 60*60*24
    
    SECONDS_UPDATE_FREQ = 60

    STATE_FRIENDS = 0
    STATE_ALBUMS = 1
    STATE_NOTIFICATIONS = 2
    STATE_MAX = 3


    def __init__(self):
        pynotify.init("name")
        self._create_gui()
        self._fbcm = FacebookCommunicationManager()
        self._fbcm.start()
        self._sb = SimpleBrowser()
        self._sb.connect("delete-event", self._login_window_closed)

        self._uid = None
        self._friends = []
        self._friend_index = {}
        self._first_friends_query = True
        self._notifications = {}
        self._notifications_first_query = True
        self._album_index = {}
        self._first_album_query = True
        self._state = 0

        gobject.timeout_add_seconds(2, self._login_start)

    def _create_left_menu(self):
        self._lmenu = gtk.Menu()
        self._loginbtn = gtk.ImageMenuItem(stock_id=gtk.STOCK_CONNECT)
        self._loginbtn.connect("activate", self._login_open_window)
        self._loginbtn.set_sensitive(False)
        
        self._lmenu.add(self._loginbtn)
        self._lmenu.show_all()

    def _create_right_menu(self):
        self._rmenu = gtk.Menu()
        about = gtk.ImageMenuItem(stock_id=gtk.STOCK_ABOUT)
        about.connect("activate", self._on_about_clicked)
        quit = gtk.ImageMenuItem(stock_id=gtk.STOCK_QUIT)
        quit.connect("activate", self._on_exit_clicked)
        self._rmenu.add(about)
        self._rmenu.add(quit)
        self._rmenu.show_all()

    def _create_gui(self):
        #load themed or fallback app icon
        try:
            icon = os.path.join(os.path.dirname(__file__),'facebook.png')
            self.icon = gtk.gdk.pixbuf_new_from_file(icon)
        except gobject.GError:
            self.icon = gtk.icon_theme_get_default().load_icon(gtk.STOCK_NETWORK, 24, 0)

        #build tray icon
        self.tray = gtk.StatusIcon()
        self.tray.set_from_pixbuf(self.icon)
        self.tray.connect('popup-menu', self._on_popup_menu)
        self.tray.connect('activate', self._on_activate)
        self.tray.set_visible(True)
        
        #create popup menus
        self._create_left_menu()
        self._create_right_menu()

    def __update_friend_index(self, new):
        self._friend_index = {}
        self._friends = new
        for f in self._friends:
            self._friend_index[f['uid']] = f

    def __update_album_index(self, new, first):
        if first:
            self._album_index = {}
            for n in new:
                self._album_index[n['aid']] = n
            return [], []
        else:
            album_index = {}
            new_albums = []
            mod_albums = []
            for n in new:
                if n['aid'] in self._album_index:
                    if n != self._album_index[n['aid']]:
                        mod_albums.append(n)
                else:
                    new_albums.append(n)
                album_index[n['aid']] = n
            self._album_index = album_index
            return new_albums, mod_albums
            

    def __send_notification(self, title, message, pic, timeout):
        #attach the libnotification bubble to the tray
        n = pynotify.Notification(title, message, pic)
        n.attach_to_status_icon(self.tray)
        n.set_timeout(timeout)
        print "Showing notification...\n   -> %s" % message
        n.show()
        return False

    def _got(self, path, title, message, timeout):
        if path:
            pic = "file://%s" % path
        else:
            pic = None
        gobject.idle_add(self.__send_notification, title, message, pic, timeout)

    def _send_notification(self, title, message, pic, timeout):
        if pic:
            self._fbcm.download_photo(
                        self._got,
                        pic,
                        title,message,timeout,
            )
        else:
            gobject.idle_add(self.__send_notification, title, message, pic, timeout)

    def _set_tooltip(self, msg):
        gobject.idle_add(self.tray.set_tooltip, msg)

    def _on_popup_menu(self, status, button, time):
        self._rmenu.popup(None, None, gtk.status_icon_position_menu, button, time, self.tray)

    def _on_activate(self, *args):
        self._lmenu.popup(None, None, gtk.status_icon_position_menu, 1, gtk.get_current_event_time(), self.tray)

    def _login_start(self):
        self._set_tooltip("Connecting to Facebook...")
        self._fbcm.call_facebook_function(
                self._login_got_auth_token,
                "auth.createToken"
        )
        #run once
        return False

    def _login_got_auth_token(self, result):
        if result:
            self._set_tooltip("Ready to Login")
            self._loginbtn.set_sensitive(True)
        else:
            self._set_tooltip("Error Connecting to Facebook")

    def _login_open_window(self, *args):
        self._sb.open_url(
                    self._fbcm.get_login_url(), 
                    None
        )

    def _login_window_closed(self, *args):
        self._set_tooltip("Logging into Facebook...")
        self._fbcm.call_facebook_function(
                    self._login_got_session,
                    "auth.getSession")
        #FIXME: Stop the login window being destoyed to prevent segfault
        self._sb.hide()
        return True

    def _login_got_session(self, result):
        if result and result.get("session_key") and result.get('uid'):
            self._uid = result.get('uid')

            self._set_tooltip("Logged into Facebook")
            self._loginbtn.set_sensitive(False)

            #get my details, se we have a photo
            self._fbcm.call_facebook_function(
                self._got_me,
                "fql.query",
                "SELECT uid, name, status, pic_small, pic_square, wall_count, notes_count, profile_update_time FROM user WHERE uid = %s" % (
                    self._uid,
                )
            )

            #check notifications now
            self._fbcm.call_facebook_function(
                    self._got_notifications,
                    "notifications.get"
            )
            
            #schdule other checks for the future
            gobject.timeout_add_seconds(
                        self.SECONDS_UPDATE_FREQ,
                        self._do_update
            )
        else:
            self._set_tooltip("Error Logging into Facebook")

    def _do_update(self):
        if self._state == self.STATE_FRIENDS:
            self._fbcm.call_facebook_function(
                self._got_friends,
                "fql.query",
                "SELECT uid, name, status, pic_small, pic_square, wall_count, notes_count, profile_update_time FROM user WHERE uid = %s OR uid IN (SELECT uid2 FROM friend WHERE uid1 = %s) ORDER BY uid DESC" % (
                    self._uid,
                    self._uid,
                )
            )
        if self._state == self.STATE_ALBUMS:
            self._fbcm.call_facebook_function(
                    self._got_fql_albums,
                    "fql.query",
                    "SELECT aid, owner, modified, size FROM album WHERE owner IN (SELECT uid2 FROM friend WHERE uid1 = %s) and size > 0 and modified > (now() - %s)" % (
                        self._uid,
                        self.SECONDS_1_DAY*5
                        )
            )
        if self._state == self.STATE_NOTIFICATIONS:
            self._fbcm.call_facebook_function(
                    self._got_notifications,
                    "notifications.get"
            )
        self._state = (self._state + 1) % self.STATE_MAX

        #keep running
        return True

    def _got_me(self, result):
        #data returned by facebook
        #{u'status': {u'message': u'is fuck Israel.', u'status_id': u'42439154725', 
        #u'time': u'1231563128'}, u'wall_count': u'144', u'uid': u'507455752', 
        #u'pic_square': u'http://profile.ak.facebook.com/v223/111/10/q507455752_2044.jpg', 
        #u'pic_small': u'http://profile.ak.facebook.com/v223/111/10/t507455752_2044.jpg', 
        #u'profile_update_time': u'1232016849', u'notes_count': u'17', u'name': u'John Stowers'}
        if result:
            print "   -> got my details"
            self._friend_index[self._uid] = result[0]

    def _got_friends(self, result):
        #data returned by facebook
        #{u'status': {u'message': u'is fuck Israel.', u'status_id': u'42439154725', 
        #u'time': u'1231563128'}, u'wall_count': u'144', u'uid': u'507455752', 
        #u'pic_square': u'http://profile.ak.facebook.com/v223/111/10/q507455752_2044.jpg', 
        #u'pic_small': u'http://profile.ak.facebook.com/v223/111/10/t507455752_2044.jpg', 
        #u'profile_update_time': u'1232016849', u'notes_count': u'17', u'name': u'John Stowers'}
        if result and result != self._friends:
            if self._first_friends_query:
                print "   -> first run"
                self._first_friends_query = False
            else:
                print "   -> friend changes detected"
                num_result = len(result)
                num_friends = len(self._friends)

                if num_result == num_friends:

                    for i in range(num_result):
                        if result[i] != self._friends[i]:
                            for k in result[i].keys():
                                print "   -> %s: %s v %s" % (k, result[i][k], self._friends[i][k])

                    changed = [i for i in range(num_result) if result[i] != self._friends[i]]
                    if len(changed) == 1:
                        idx = changed[0]
                        name = result[idx]["name"]
                        pic = result[idx]["pic_square"]

                        if  result[idx]["status"] and \
                            self._friends[idx]["status"] and \
                            result[idx]["status"]["message"] != self._friends[idx]["status"]["message"]:
                            msg = "%s updated their status\n\n<i>%s</i>" % (name, result[idx]["status"]["message"])
                        elif result[idx]["pic_square"] != self._friends[idx]["pic_square"]:
                            msg = "%s changed their profile picture" % name
                        elif result[idx]["wall_count"] != self._friends[idx]["wall_count"]:
                            diff = int(result[idx]["wall_count"]) - int(self._friends[idx]["wall_count"])
                            if diff == 1:
                                msg = "Someone wrote on %s's wall" % name
                            else:
                                msg = "%s people wrote on %s wall" % (diff, name)
                        elif result[idx]["notes_count"] != self._friends[idx]["notes_count"]:
                            msg = "%s posted a new note" % name
                        else:
                            msg = "%s updated his/her profile" % name
                    elif len(changed) < 5:
                        names = [result[i]["name"] for i in changed]
                        msg = "%s and %s updated their profiles" % (", ".join(names[0:-1]), names[-1])
                        pic = None
                    else:
                        msg = "%s friends updated their profiles" % len(changed)
                        pic = None
                else:
                    msg = "You gained or lost a friend"
                    pic = None

                self._send_notification(
                        title="Friends",
                        message=msg,
                        pic=pic,
                        timeout=pynotify.EXPIRES_DEFAULT
                )

            self.__update_friend_index(result)


    def _got_fql_albums(self, result):
        #data returned by facebook
        #[{u'owner': u'1546153065', u'aid': u'6640676848787171224', u'modified': u'1232092931', u'size': u'1'},...]
        if result:
            if self._first_album_query:
                print "   -> first run"

            new_albums, mod_albums = self.__update_album_index(result, self._first_album_query)
            self._first_album_query = False

            friends = []
            if new_albums or mod_albums:
                print "   -> album changes detected"
                for n in new_albums+mod_albums:
                    f = self._friend_index.get(n['owner'])
                    if f:
                        friends.append(f)

                if len(friends) == 1:
                    msg = "%s uploaded new photos" % friends[0]['name']
                    pic = friends[0]['pic_square']
                else:
                    names = [f['name'] for f in friends]
                    msg = "%s and %s uploaded new photos" % (", ".join(names[0:-1]), names[-1])
                    pic = None

                self._send_notification(
                        title="Albums",
                        message=msg,
                        pic=pic,
                        timeout=pynotify.EXPIRES_DEFAULT
                )


    def _got_notifications(self, result):
        #data returned by facebook
        #{
        #   u'pokes': {u'most_recent': u'0', u'unread': u'0'}, 
        #   u'messages': {u'most_recent': u'1230001286', u'unread': u'0'}, 
        #   u'shares': {u'most_recent': u'0', u'unread': u'0'}, 
        #   u'group_invites': [], 
        #   u'event_invites': [], 
        #   u'friend_requests': [u'1106512525']}
        if result and result != self._notifications:
            print "   -> notification changes detected"
            msgs = []

            pokes = result.get('pokes',{}).get('unread', '0')
            if pokes and int(pokes) > 0:
                msgs.append("<i>%s pokes</i>" % pokes)

            messages = result.get('messages',{}).get('unread', 0)
            if messages and int(messages) > 0:
                msgs.append("<i>%s messages</i>" % messages)

            shares = result.get('shares',{}).get('unread', 0)
            if shares and int(shares) > 0:
                msgs.append("<i>%s shares</i>" % messages)

            group = result.get('group_invites', [])
            if group:
                msgs.append("<i>%s group invites</i>" % len(group))

            event = result.get('event_invites', [])
            if event:
                msgs.append("<i>%s event invites</i>" % len(event))

            friend = result.get('friend_requests', [])
            if friend:
                msgs.append("<i>%s friend requests</i>" % len(friend))

            if msgs:
                self._send_notification(
                        title="Notifications",
                        message="You have\n" + "\n".join(msgs),
                        pic=self._friend_index[self._uid]["pic_square"],
                        timeout=pynotify.EXPIRES_DEFAULT
                )
            elif self._notifications_first_query:
                self._send_notification(
                        title="Facebook",
                        message="You have logged in successfully",
                        pic=self._friend_index[self._uid]["pic_square"],
                        timeout=2000
                )

            self._notifications_first_query = False
            self._notifications = result

    def _on_about_clicked(self, widget):
        dlg = gtk.AboutDialog()
        dlg.set_name("Facebook Notifier")
        dlg.set_logo(self.icon)
        dlg.run()
        dlg.destroy()

    def _on_exit_clicked(self, widget):
        self._fbcm.stop()
        gtk.main_quit()

if __name__ == "__main__":
    gtk.gdk.threads_init()
    app = Gui()
    gtk.main()

