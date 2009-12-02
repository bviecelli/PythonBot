#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import socket
import sys
import urllib2
import os
import time
import traceback
from pysqlite2 import dbapi2 as sqlite

DATA_LIMIT = 262144
DATA_CHUNK = 1024

ENCODING = 'utf-8'
FALLBACK_ENCODING = 'iso-8859-1'

channel = '#masmorra'
nick = 'carcereiro'
server = 'irc.oftc.net' 

def sendcmd(cmd, middle, trail=None):
	m = '%s ' % (cmd)
	for a in middle:
		m += '%s ' % (a)
	if trail is not None:
		m += ':%s' % (trail)
	m += '\r\n'
	print "*** sending data: %r" % (m)
	sock.send(m)

def _sendmsg(who, msg): 
	sendcmd('PRIVMSG', [who], unicode(msg).encode(ENCODING))

def sendmsg(msg):
    return _sendmsg(channel, msg)

class db():
	def __init__(self, dbfile):
		if not os.path.exists(dbfile):
			self.conn = sqlite.connect(dbfile)
			self.cursor = self.conn.cursor()
			self.create_table()
		self.conn = sqlite.connect(dbfile)
		self.cursor = self.conn.cursor()
	def close(self):
		self.cursor.close()
		self.conn.close()
	def create_table(self):
		self.cursor.execute('CREATE TABLE karma(nome VARCHAR(30) PRIMARY KEY, total INTEGER);')
		self.cursor.execute('CREATE TABLE url(nome VARCHAR(30) PRIMARY KEY, total INTEGER);')
		self.cursor.execute('CREATE TABLE slack(nome VARCHAR(30), total INTEGER, data DATE, PRIMARY KEY (data, nome));')
		self.conn.commit()
	def insert_karma(self,nome,total):
		try:
			self.cursor.execute("INSERT INTO karma(nome,total) VALUES ('%s', %d );" % (nome,total))
			self.conn.commit()
			return True
		except:
			#print "Unexpected error:", sys.exc_info()[0]
			return False
	def change_karma(self,nome,amount):
		if not self.insert_karma(nome,amount):
			self.cursor.execute("UPDATE karma SET total = total + (%d) where nome = '%s';" % (amount, nome))
			self.conn.commit()
	def increment_karma(self,nome):
		return self.change_karma(nome, 1)
	def decrement_karma(self,nome):
		return self.change_karma(nome, -1)
	def insert_url(self,nome,total):
		try:
			self.cursor.execute("INSERT INTO url(nome,total) VALUES ('%s', %d );" % (nome,total))
			self.conn.commit()
			return True
		except:
			return False
	def increment_url(self,nome):
		if not self.insert_url(nome,1):
			self.cursor.execute("UPDATE url SET total = total + 1 where nome = '%s';" % (nome))
			self.conn.commit()
	def insert_slack(self,nome,total):
		try:
			self.cursor.execute("INSERT INTO slack(nome,total,data) VALUES ('%s', %d, '%s' );" % (nome,total,time.strftime("%Y-%m-%d", time.localtime())))
			self.conn.commit()
			return True
		except:
			return False
	def increment_slack(self,nome,total):
		if not self.insert_slack(nome,total):
			self.cursor.execute("UPDATE slack SET total = total + %d where nome = '%s' and data = '%s' ;" % (total,nome,time.strftime("%Y-%m-%d", time.localtime())))
			self.conn.commit()
	def get_karmas_count(self, desc=True, max_len=400):
		q = 'SELECT nome,total FROM karma order by total'
		if desc:
			q += ' desc'
		self.cursor.execute(q)
		karmas = ''
		for linha in self.cursor:
			item = (linha[0]) + ' = ' + unicode(linha[1])
			if len(karmas) == 0:
				append = item
			else:
				append = ', ' + item
			if len(karmas) + len(append) > max_len:
				break
			karmas += append
		return karmas
	def get_karmas(self):
		self.cursor.execute('SELECT nome FROM karma order by total desc')
		karmas = ''
		for linha in self.cursor:
			if len(karmas) == 0:
				karmas = (linha[0])
			else:	
				karmas = karmas + ', ' + (linha[0])
		return karmas
	def get_karma(self, nome):
		self.cursor.execute("SELECT total FROM karma where nome = '%s'" % (nome))
		for linha in self.cursor:
				return (linha[0])
	def get_urls_count(self):
		self.cursor.execute('SELECT nome,total FROM url order by total desc')
		urls = ''
		for linha in self.cursor:
			if len(urls) == 0:
				urls = (linha[0]) + ' = ' + unicode(linha[1])
			else:
				urls = urls + ', ' + (linha[0]) + ' = ' + unicode(linha[1])
		return urls
	def get_slacker_count(self):
		self.cursor.execute("SELECT nome,total FROM slack where data = '%s' order by total desc" % (time.strftime("%Y-%m-%d", time.localtime())))
		slackers = ''
		for linha in self.cursor:
			if len(slackers) == 0:
				slackers = (linha[0]) + ' = ' + unicode(linha[1])
			else:
				slackers = slackers + ', ' + (linha[0]) + ' = ' + unicode(linha[1])
		return slackers


def try_unicode(s, enc_list):
	for e in enc_list:
		try:
			return unicode(s, e)
		except:
			pass

	# no success:
	return unicode(s, enc_list[0], 'replace')

def data_as_unicode(resp, s):
	info = resp.info()
	try:
		ctype,charset = info['Content-Type'].split('charset=')  
	except:
		charset = ENCODING

	return try_unicode(s, [charset, ENCODING, FALLBACK_ENCODING])

class html:
	def __init__(self, url):
		self.url = url
		self.headers = {
	      'User-Agent' : 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.7.10)',
   	   'Accept-Language' : 'pt-br,en-us,en',
      	'Accept-Charset' : 'utf-8,ISO-8859-1'
	   }
	def title(self):
		reqObj = urllib2.Request(self.url, None, self.headers)
		self.urlObj = urllib2.urlopen(reqObj)
		self.resp_headers = self.urlObj.info()
		print '*** headers:',repr(self.resp_headers.items())

		ctype = self.resp_headers.get('content-type', '')
		print '*** content type: %r' % (ctype)

		if ctype.startswith('image/'):
			return u"olha, uma imagem!"

		if ctype.startswith('audio/'):
			return u"eu não tenho ouvidos, seu insensível!"

		if 'html' in ctype or 'xml' in ctype:
			title_pattern = re.compile(r"<title[^>]*?>(.*?)< */ *title *>", re.UNICODE|re.MULTILINE|re.DOTALL|re.IGNORECASE)
			data = ''
			while True:
				if len(data) > DATA_LIMIT:
					break

				d = self.urlObj.read(DATA_CHUNK)
				if not d:
					break

				data += d

				udata = data_as_unicode(self.urlObj, data)

				title_search = title_pattern.search(udata)
				if title_search is not None:
					title = title_search.group(1)
					title = title.strip().replace("\n"," ").replace("\r", " ")
					title = re.sub("&#?\w+;", "", title)
					print '*** title: ',repr(title)
					return u"[ %s ]" % (title)
			# no title found
			return None

		return u"%s? o que é isso?" % (ctype)


password = sys.argv[1]

banco = db('carcereiro.db')
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((server, 6667))
sock.settimeout(900)

# initially use nick_ (I hope nobody will connect using it :)
sock.send('NICK %s_ \r\n' % nick)
sock.send('USER %s \'\' \'\' :%s\r\n' % (nick, 'python'))

# regain nick, if it is in use
sock.send('NICKSERV REGAIN %s %s\r\n' % (nick, password))

# change to the real nick
sock.send('NICK %s \r\n' % nick)
sock.send('NICKSERV IDENTIFY %s\r\n' % (password))

# join the channel
sock.send('JOIN %s \r\n' % channel)


def do_karma(r):
	var = r.group(1)
	banco.increment_karma(var)
	if var == nick:
		sendmsg('eu sou foda! ' + unicode(banco.get_karma(var)) + ' pontos de karma')
	else:
		sendmsg(var + ' now has ' + unicode(banco.get_karma(var)) + ' points of karma')

def do_karma_sum(r):
	var,sign,amount = r.groups()
	amount = int(amount)
	if amount > 20:
		sendmsg(u'%d pontos de uma vez? tá doido!?' % (amount))
		return
	if amount > 1:
		sendmsg(u'%d pontos de uma vez é demais' % (amount))
		return
	if sign == '-':
		amount = -amount
	banco.change_karma(var, amount)
	sendmsg(var + ' now has ' + unicode(banco.get_karma(var)) + ' points of karma')

def do_slack(r):
	var = len(r.group(2)) - 1
	nick = r.group(1)
	banco.increment_slack(nick,var)
	# continue handling other regexps
	return True


def do_dec_karma(resultm):
	var = resultm.group(1)
	banco.decrement_karma(var)
	if var == nick:
		sendmsg('tenho ' + unicode(banco.get_karma(var)) + ' pontos de karma agora  :(')
	else:
		sendmsg(var + ' now has ' + unicode(banco.get_karma(var)) + ' points of karma')


def do_show_karma(resultk):
	var = resultk.group(1)
	points = banco.get_karma(var)
	if points is not None:
		sendmsg(var + ' have ' + unicode(points) + ' points of karma')
	else:
		sendmsg(var + ' doesn\'t have any point of karma')

def do_dump_karmas(r):
	sendmsg('high karmas: ' + banco.get_karmas_count(True))
	sendmsg('low karmas: ' + banco.get_karmas_count(False))

def do_slackers(r):
	sendmsg('slackers in chars : ' + banco.get_slacker_count())

def do_urls(r):
	sendmsg('users : ' + banco.get_urls_count())

def do_url(url_search):
	try:
		url  = url_search.group(2).encode('utf-8')
		nick = url_search.group(1)
		print "*** Getting URL %r ..." % (url)
		print '*** url: %r' % (url)
		try:
			parser = html(url)
			t = parser.title()
		except urllib2.URLError,e:
			t = u"ui. erro. o servidor não gosta de mim (%s)" % (str(e))
			traceback.print_exc()
		except Exception,e:
			t = u"acho que algo explodiu aqui. :( -- %s" % (str(e))
			print "*** Unexpected error:", sys.exc_info()[0]
			traceback.print_exc()

		if not t:
			t = u"não consegui achar o título. desculpa tio  :("

		sendmsg(t)
		banco.increment_url( nick )
	except:
		sendmsg('[ Failed ]')
		print url
		print "*** Unexpected error:", sys.exc_info()[0]
		traceback.print_exc()

sender_re = re.compile('([^!@]+)((![^!@]+)?)((@[^!@]+)?)')

class Message:
	def __init__(self, sender, cmd, middleargs, arg):
		self.sender = sender
		self.cmd = cmd
		self.middleargs = middleargs
		self.arg = arg

		m = sender_re.match(self.sender)
		if not m:
			print "***** sender regexp doesn't match?"
			self.sender_nick = self.sender
			self.sender_user = self.sender_host = ''
		else:
			self.sender_nick = m.group(1)
			self.sender_user = m.group(2).lstrip('!')
			self.sender_host = m.group(4).lstrip('@')

	def __repr__(self):
		return '<message: cmd %r from [%r]![%r]@[%r]. middle: %r. arg: %r>' % (self.cmd, self.sender_nick, self.sender_user, self.sender_host, self.middleargs, self.arg)


def handle_privmsg(m):
	target, = m.middleargs
	print "***** privmsg received: %r" % (m)

def handle_ping(m):
	print "PING %r" % (m)

# handler for each command type. keys are in lower case
cmd_handlers = {
	'privmsg':handle_privmsg,
	'ping':handle_ping,
}

def cmd_received(r):
	groups = r.groups()
	sender,cmd,middle,_,trailing = groups
	middleargs = middle.split()

	m = Message(sender, cmd, middleargs, trailing)
	print '*** cmd received: ', repr(m)

	h = cmd_handlers.get(m.cmd.lower())
	if h:
		h(m)

	# continue handling the legacy regexps
	return True


# regexes for IRC commands:
regexes = [
	('^:([^ ]*) +([a-zA-Z]+) +(([^:][^ ]* +)*):(.*)\r*\n*$', cmd_received),
	(':([a-zA-Z0-9\_]+)!.* PRIVMSG.* :(.*)$', do_slack),
	('''(?i)PRIVMSG.*[: ](g|google|)\.*wave--''', lambda r: sendmsg(u'o Google Wave é uma merda mesmo, todo mundo já sabe') or True),
	('PRIVMSG.*[: ](\w(\w|[._-])+)\+\+', do_karma),
	('PRIVMSG.*[: ](\w(\w|[._-])+)\-\-', do_dec_karma),
	('PRIVMSG.*[: ](\w\w+) *(\+|-)= *([0-9]+)', do_karma_sum),
	('PRIVMSG.*:karma (\w+)', do_show_karma),
	('PRIVMSG.*[: ]\@karmas', do_dump_karmas),
	('PRIVMSG.*[: ]\@slackers', do_slackers),
	('PRIVMSG.*[: ]\@urls', do_urls),
	('(?i)PRIVMSG.*[: ]ronaldo!', lambda r: sendmsg(u'brilha muito nu curintia!')),
	('(?i)PRIVMSG.*[: ]curintia!', lambda r: sendmsg(u'brilha muito no ronaldo!')),
	('(?i)PRIVMSG.*[: ]coraldo!', lambda r: sendmsg(u'brilha muito no ronintia!')),
	('''(?i)PRIVMSG [#a-z_-]+ :tu[ -]*dum[\.!]*\r*\n*$''', lambda r: sendmsg(u'PÁ!')),
	(u'''(?i)PRIVMSG [#a-z_-]+ :o* *meu +pai +(é|e)h* +detetive[\.!]*\r*\n*$''', lambda r: sendmsg(u'mas o teu é despachante')),
	(u'''(?i)PRIVMSG.*ningu[ée]m f(a|e)z nada!''', lambda r: sendmsg(u'ninguém f%sz nada! NA-DA!' % (r.group(1)))),
	('(?i)PRIVMSG.*[: ]jip(e|inho) +tomb(a|ou)', lambda r: sendmsg(u'nao fala em jipe tombar!')),
	('(?i)PRIVMSG.*[: ](bot|carcereiro) burro', lambda r: sendmsg(":'(")),
	('PRIVMSG.*[: ]/wb/', lambda r: sendmsg(u'eu não tenho acesso ao /wb/, seu insensível!')),
	(':([a-zA-Z0-9\_]+)!.* PRIVMSG .*?(https?://[^ \t>\n\r\x01-\x1f]+)', do_url),
	('(?i)PRIVMSG.*[: ](carcereiro|carcy)', lambda r: sendmsg('eu?')),
]

compiled_res = []
# compile all regexes:
for e,f in regexes:
	cr = re.compile(e, re.UNICODE)
	compiled_res.append( (cr, f) )


newline = re.compile('\r*\n')
def readlines(sock):
	buf = ''
	while True:
		data = sock.recv(2040)
		if not data:
			print "**** no returned data. EOF?"
			break
		print '* raw data: ',repr(data)
		buf += data
		while newline.search(buf):
			line,rest = newline.split(buf, 1)
			print "** line: %r" % (line)
			print "** rest: %r" % (rest)
			yield line
			buf = rest

for line in readlines(sock):
	if line.find('PING') != -1:
		sock.send('PONG ' + line.split() [1] + '\r\n')

	if re.search(':[!@]help', line, re.UNICODE) is not None or re.search(':'+nick+'[ ,:]+help', line, re.UNICODE) is not None:
		sendmsg('@karmas, @urls, @slackers\r\n')

	msg = try_unicode(line, [ENCODING, FALLBACK_ENCODING])

	for exp,fn in compiled_res:
		r = exp.search(msg)
		if r:
			try:
				res = fn(r)
				if not res:
					break
			except Exception,e:
				print "***** Message handler error: "
				traceback.print_exc()
				



sock.close()
banco.close()
