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

import time
import os.path

import gobject
import gtk
import pynotify

import libfacebooknotify.comm as comm
from libfacebooknotify import   APP_NAME, APP_DESCRIPTION, APP_VERSION, APP_AUTHORS, APP_HOMEPAGE, APP_LICENSE

# import the backend module
EW_BACKEND = None
try:
    # try to import Gecko module first
    import gtkmozembed
    EW_BACKEND = "gtkmozembed"
except:
    # if that fails, try webkit
    import webkit
    EW_BACKEND = "webkit"

class BrowserEmbed:

    def __init__(self):
        self._embed_widget = None
        print "browser using: %s" % EW_BACKEND
        if EW_BACKEND == "webkit":
            self._embed_widget = webkit.WebView()
            #disable flash to stop segfault on destroy
            self._embed_widget.get_settings().props.enable_plugins = False
        elif EW_BACKEND == "gtkmozembed":
            self._embed_widget = gtkmozembed.MozEmbed()

    def open_url(self, url):
        if EW_BACKEND == "webkit":
            return self._embed_widget.open(url)
        elif EW_BACKEND == "gtkmozembed":
            return self._embed_widget.load_url(url)
        else:
            raise Exception('No valid backend available')

    def get_widget(self):
        return self._embed_widget

class SimpleBrowser(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.isLoginRequest = False
        self._sw = gtk.ScrolledWindow()

        self._bv = BrowserEmbed()

        self._sw.add_with_viewport(self._bv.get_widget())
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC);
        self.add(self._sw)

    def _move_window_to_status_icon(self, si):
        screen, pos, orientation = si.get_geometry()
        #window.set_gravity(gtk.gdk.GRAVITY_SOUTH_EAST)
        #width, height = window.get_size()
        #window.move(gtk.gdk.screen_width() - width, gtk.gdk.screen_height() - height)


    def open_url(self, url, statusIcon=None, isLoginRequest=False):
        self.isLoginRequest = isLoginRequest
        if statusIcon and statusIcon.is_embedded():
            self._move_window_to_status_icon(statusIcon)
        else:
            self.set_position(gtk.WIN_POS_CENTER)
        self.set_size_request(800,600)
        self._bv.open_url(url)
        self.show_all()

class HistoryMenuItem(gtk.ImageMenuItem):
    def __init__(self, title, message, pic):
        gtk.ImageMenuItem.__init__(self, stock_id=gtk.STOCK_DIALOG_INFO)

        self.set_tooltip_markup(message)

        if pic:
            pb = gtk.gdk.pixbuf_new_from_file_at_size(
                            pic.replace("file://",""),
                            *gtk.icon_size_lookup(gtk.ICON_SIZE_MENU))
            self.set_image(gtk.image_new_from_pixbuf(pb))

        lbl = self.get_children()[0]
        lbl.set_text(title)

        #remove the label, and place it in a hbox
        self.remove(lbl)

        hb = gtk.HBox()
        hb.pack_start(lbl, True, True)

        #add another label beside it, that shows the time this item was added
        mtime = gtk.Label('<span style="italic" weight="light">%s</span>' % time.strftime("%I:%M %p"))
        mtime.props.xalign = 1.0
        mtime.props.use_markup = True
        hb.pack_start(mtime, False, False)
        
        self.add(hb)
        
class Gui:

    SECONDS_1_MIN = 60
    SECONDS_1_HOUR = 60*60
    SECONDS_1_DAY = 60*60*24
    
    SECONDS_UPDATE_FREQ = 60

    STATE_FRIENDS = 0
    STATE_ALBUMS = 1
    STATE_NOTIFICATIONS = 2
    STATE_NOTIFICATIONSLIST = 3
    STATE_MAX = 4

    HISTORY_MAX = 5

    def __init__(self):
        pynotify.init(APP_NAME)
        self._create_gui()
        self._fbcm = comm.FacebookCommunicationManager()
        self._fbcm.start()
        self._sb = SimpleBrowser()
        self._sb.connect("delete-event", self._login_window_closed)

        self._uid = None
        self._friends = []
        self._friend_index = {}
        self._first_friends_query = True
        self._notifications = {}
        self._notifications_first_query = True
        self._notifications_show_actions = 'actions' in pynotify.get_server_caps()
        self._notificationslist = {}
        self._notifications_lasttime = 0
        self._album_index = {}
        self._first_album_query = True
        self._state = 0

        gobject.timeout_add_seconds(2, self._login_start)

    def _create_left_menu(self):
        self._lmenu = gtk.Menu()
        self._loginbtn = gtk.ImageMenuItem(stock_id=gtk.STOCK_DIALOG_AUTHENTICATION)
        self._loginbtn.get_children()[0].set_text("Login to Facebook")
        self._loginbtn.connect("activate", self._login_open_window)
        self._loginbtn.set_sensitive(False)

        self._homebtn = gtk.ImageMenuItem(stock_id=gtk.STOCK_HOME)
        self._homebtn.get_children()[0].set_text("Open Facebook Homepage")
        self._homebtn.connect(
                "activate", 
                lambda x: self._sb.open_url("http://x.facebook.com/")
        )
        self._homebtn.set_sensitive(False)

        self._lmenu.add(self._loginbtn)
        self._lmenu.add(self._homebtn)

        self._lmenu.add(gtk.SeparatorMenuItem())
        title = gtk.MenuItem("Notification History")
        #right align the label inside the MenuItem
        title.get_children()[0].props.xalign = 1.0
        title.set_sensitive(False)
        self._lmenu.add(title)
        self._lmenu_summaries = []

        self._lmenu.show_all()

    def _add_lmenu_notification_summary(self, title, message, pic, url):
        if len(self._lmenu_summaries) == self.HISTORY_MAX:
            item = self._lmenu_summaries[0]
            self._lmenu_summaries.remove(item)
            self._lmenu.remove(item)

        new = HistoryMenuItem(title, message, pic)
        self._lmenu.add(new)
        self._lmenu_summaries.append(new)
        new.show_all()

    def _create_right_menu(self):
        self._rmenu = gtk.Menu()
        about = gtk.ImageMenuItem(stock_id=gtk.STOCK_ABOUT)
        about.connect("activate", self._on_about_clicked)
        quit = gtk.ImageMenuItem(stock_id=gtk.STOCK_QUIT)
        quit.connect("activate", self.exit)
        self._rmenu.add(about)
        self._rmenu.add(quit)
        self._rmenu.show_all()

    def _create_gui(self):
        icon_name = "facebook"

        #load themed or fallback app icon
        theme = gtk.icon_theme_get_default()
        if not theme.has_icon(icon_name):
            theme.prepend_search_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..", "icons"))
        if theme.has_icon(icon_name):
            self._icon_name = icon_name
        else:
            self._icon_name = gtk.STOCK_NETWORK

        #build tray icon
        self.tray = gtk.StatusIcon()
        self.tray.set_from_icon_name(self._icon_name)
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
            

    def __send_notification(self, title, message, pic, timeout, url):
        #add a history item to the menu
        self._add_lmenu_notification_summary(title, message, pic, url)

        #attach the libnotification bubble to the tray
        n = pynotify.Notification(title, message, pic)
        if self._notifications_show_actions and url:
            #this does not actually work, dont know why....
            n.add_action(
                "open",
                "Open Facebook",
                lambda n, action, _url: self._sb.open_url(_url),
                url
            )
        n.attach_to_status_icon(self.tray)
        n.set_timeout(timeout)
        print "Showing notification...\n   -> %s" % message
        n.show()
        return False

    def _got(self, path, title, message, timeout, url):
        if path:
            pic = "file://%s" % path
        else:
            pic = None
        gobject.idle_add(self.__send_notification, title, message, pic, timeout, url)

    def _send_notification(self, title, message, pic, timeout, url):
        if pic:
            self._fbcm.download_photo(
                        self._got,
                        pic,
                        title,message,timeout,url
            )
        else:
            gobject.idle_add(self.__send_notification, title, message, pic, timeout, url)

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
                    statusIcon=None,
                    isLoginRequest=True
        )

    def _login_window_closed(self, *args):
        if self._sb.isLoginRequest:
            self._set_tooltip("Logging into Facebook...")
            self._fbcm.call_facebook_function(
                        self._login_got_session,
                        "auth.getSession")
        #Stop the login window being destoyed so we can re-use it later, now the user has already logged in
        self._sb.hide()
        return True

    def _login_got_session(self, result):
        if result and result.get("session_key") and result.get('uid'):
            self._uid = result.get('uid')

            self._set_tooltip("Logged into Facebook")
            self._loginbtn.set_sensitive(False)
            self._homebtn.set_sensitive(True)

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
            
            # notificationslist
            self._fbcm.call_facebook_function(
            		self._got_notificationslist,
            		"fql.query",
            		"SELECT created_time, title_text, body_text, href FROM notification WHERE recipient_id=%s AND is_unread = 1 AND is_hidden = 0 AND created_time > %s" % (
            			self._uid,
            			self._notifications_lasttime
            		)
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
            
        if self._state == self.STATE_NOTIFICATIONSLIST:
            self._fbcm.call_facebook_function(
                    self._got_notificationslist,
                    "fql.query",
            		"SELECT created_time, title_text, body_text, href FROM notification WHERE recipient_id=%s AND is_hidden = 0 AND is_unread = 1 AND created_time > %s" % (
            			self._uid,
            			self._notifications_lasttime
            		)
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

    def _got_notificationslist(self, result):
    	#data returned
    	
    	#may add consolidation for notifications pertaining to same thing (via href)
    	if result and result != self._notificationslist:
    		msg = ""
    		num_result = len(result)
    		
    		if num_result > 0:
				print "   -> %d new notifications detected" % num_result
				for i in range(num_result):
					print "   -> %s" % result[i]["title_text"]
				
				if num_result == 1:
					if result[0]["body_text"] == "":
						msg = "%s" % result[0]["title_text"]
					else:
	   					msg = "%s \n\n<i>%s</i>" % (result[0]["title_text"], result[0]["body_text"])
  				else:
   					msg = "%d new notifications" % num_result
   				self._send_notification(
					title="Notifications",
					message=msg,
					pic=None,
					timeout=pynotify.EXPIRES_DEFAULT,
					url=None
	            )
	        self._notifications_lasttime = result[0]["created_time"]
	        self._notificationslist = result


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
                num_result = len(result)
                num_friends = len(self._friends)

                if num_result == num_friends:

                    changed = []
                    for i in range(num_result):
                        if result[i] != self._friends[i]:
                            has_changed = 0
                            for k in result[i].keys():
                                if result[i][k] != self._friends[i][k] and \
                                   k != 'wall_count':
                                   has_changed = 1
                            if (has_changed == 1):
                                changed.append(i)
                                for k in result[i].keys():
                                    if (result[i][k] != self._friends[i][k]):
                                        print "   -> %s: %s => %s" % (k, self._friends[i][k], result[i][k])
                                    else:
                                        print "   -> %s: %s" % (k, result[i][k])
                                print

                    print "   -> %d friend changes detected" % len(changed)

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
                    elif changed:
                        msg = "%s friends updated their profiles" % len(changed)
                        pic = None
                else:
                    msg = "You gained or lost a friend"
                    pic = None

                self._send_notification(
                        title="Friends",
                        message=msg,
                        pic=pic,
                        timeout=pynotify.EXPIRES_DEFAULT,
                        url=None
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
                        timeout=pynotify.EXPIRES_DEFAULT,
                        url=None
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
                        timeout=pynotify.EXPIRES_DEFAULT,
                        url=None
                )
            elif self._notifications_first_query:
                self._send_notification(
                        title="Logged in",
                        message="You have logged in to Facebook successfully",
                        pic=self._friend_index[self._uid]["pic_square"],
                        timeout=2000,
                        url=None
                )

            self._notifications_first_query = False
            self._notifications = result

    def _on_about_clicked(self, widget):
        #should probbably only do this once.
        gtk.about_dialog_set_url_hook(
                lambda dlg, url: self._sb.open_url(url)
        )

        dlg = gtk.AboutDialog()
        dlg.set_name(APP_NAME)
        dlg.set_comments(APP_DESCRIPTION)
        dlg.set_copyright("License: %s" % APP_LICENSE)
        dlg.set_website(APP_HOMEPAGE)
        dlg.set_version(APP_VERSION)
        dlg.set_authors(APP_AUTHORS)
        dlg.set_logo_icon_name(self._icon_name)
        dlg.run()
        dlg.destroy()

    def exit(self, *args):
        self._fbcm.stop()
        gtk.main_quit()

if __name__ == "__main__":
    gtk.gdk.threads_init()
    app = Gui()
    gtk.main()

