#!/usr/bin/python
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse
import requests, hmac, base64, struct, hashlib, time, random, socket

# Takes a secret and a time interval, returning a token.
# Success if it matches what the user provided
# pseudocode provided here: https://en.wikipedia.org/wiki/Google_Authenticator

# ***********************************************************************^ #
#  WARNING: This code is for algorithm demonstration only, it is insecure  #
# ************************************************************************ #

HOST_URL = '' # Set when the server starts, global for self test
SECRETS = {'unknown':'MZXW633PN5XW6MZX'} # Key is username, value is the user's secret
HOTP_COUNTER = 123456 # Not very secure 1) guessable 2) all SECRETS share
HOTP_SKEW = 10 # Range that we allow for over active client

def get_otp_token(secret, counter):
    # Calculation the OATH value
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", counter)
    hash = hmac.new(key, msg, hashlib.sha1).digest()
    offset = hash[19] & 15
    code = (struct.unpack(">I", hash[offset:offset+4])[0] & 0x7fffffff) % 1000000
    return str('%06d' % code)

def generateSecret():
    # Using 16 random base32 characters
    return ''.join(random.SystemRandom().choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567') for _ in range(16))

def timeInterval():
    return int(time.time()/30)

def currentHOTP(name='unknown'):
    # HMAC based OATH authenication
    return get_otp_token(SECRETS.get(name,'unknown'), HOTP_COUNTER)

def currentTOTP(name='unknown'):
    # TIME based OATH authenication
    return get_otp_token(SECRETS.get(name,'unknown'), timeInterval())

def rolloverTOTP(name='unknown'):
    # Demostrate TOTP rollover to next time interval
    remaining = time.time() % 30
    print('code=%s seconds to rollover=%d' % (currentTOTP(name),remaining))
    time.sleep(remaining+1)
    print('code=%s' % (currentTOTP(name)))
    return

def validateHOTP(query_components):
    # Validate user's HOTP attempt
    global HOTP_COUNTER
    code = query_components.get('code')
    name = query_components.get('name','unknown')  
    for i in range(HOTP_COUNTER,HOTP_COUNTER+HOTP_SKEW):
        if code == get_otp_token(SECRETS.get(name,'unknown'), i):
            HOTP_COUNTER = i + 1
            return 'Validated'
    return 'Failed'

def validateTOTP(query_components):
    # Validate user's TOTP attempt, no consideration for clock skew
    code = query_components.get('code')
    name = query_components.get('name','unknown')
    if code == get_otp_token(SECRETS.get(name,'unknown'), timeInterval()):
        return 'Validated' 
    return 'Failed'

def registerUser(query_components):
    # Add a new user
    user = query_components.get('name')
    secret = query_components.get('secret')
    SECRETS[user] = secret
    return user + ' registered with secret: ' + secret

def showQR(secret, name):
    gURL = 'https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl='
    gArg = '/validateTOTP?' + name + '?secret=' + secret
    html = requests.get(gURL + HOST_URL + gArg)
    return html
	
def defaultPage(query_components):
    name = query_components.get('name', 'unknown')
    secret = SECRETS.get(name)
    if secret == None:
        name = 'unknown'
        secret = SECRETS.get(name)
        
    gURL = 'https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl'
    gArg = '/validateTOTP?' + name + '&secret=' + secret
    qrURL = gURL + HOST_URL + gArg
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<script type="text/javascript">
function load() {
var secret = '""" + secret + """';
var name = '""" + name + """';
document.getElementById('qr_image').src = '""" + qrURL + """';
}
</script>
<body onload="load()"><h1>Validate Device</h1>
<h3>Current TOTP for (""" + name + '): ' + currentTOTP(name) + """</h3>
<h3>Current HOTP: """ + currentHOTP(name) +  "&nbsp;&nbsp;HOTP Counter: " + str(HOTP_COUNTER) + """<h3>
<img src="nothing.jpg" id="qr_image" name="qr_image"/>
<form action="/registerUser">
  <label for="username">Register User:</label>
  <input type="text" name="name" placeholder="username">
  <label for="secret">Secret:</label>
  <input type="text" name="secret" value='""" + generateSecret() + """'>
  <input type="submit" value="registerUser">
</form>
<form action="/validateTOTP">
    <label for="username">Validate TOPT for user:</label>
    <input type="text" name="name" placeholder="username">
    <label for="code">Code:</label>
    <input type="text" name="code" placeholder='code'>
    <input type="submit" value="validateTOTP">
</form>
<form action="/validateHOTP">
    <label for="username">Validate HOPT for user:</label>
    <input type="text" name="name" placeholder="username">
    <label for="code">Code:</label>
    <input type="text" name="code" placeholder='code'>
    <input type="submit" value="validateHOTP">
</form>
<h1>How to use this service</h1>
Replace [yoursecret] with your 16 character base32 value<br/>
Add new account: """ + HOST_URL + """/registerUser?name=[yourname]?secret=[yoursecret]<br/>
Validate TOPT: """ + HOST_URL + """/validateTOTP?name=[yourname]?code=[your topt code]<br/>
Validate HOPT: """ + HOST_URL + """/validateHOTP?name=[yourname]?code=[your hopt code]</body></html>"""
    return html

action_statements = {
    "/registerUser": registerUser,
    "/validateHOTP": validateHOTP,
    "/validateTOTP": validateTOTP,
}

#This class will handles any incoming request from the browser 
class OTPserver(BaseHTTPRequestHandler):

    #Handler for the GET requests
    def do_GET(self):
        # Everything returns 200 OK
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()

        action = urlparse(self.path).path
        method = action_statements.get(action,defaultPage)
        
        if method == None : return
        
        try:
            query = urlparse(self.path).query
            query_components = dict(qc.split("=") for qc in query.split("&"))
        except ValueError:
            # Missing or malformed query string so use an empty dictionary
            query_components = {"":""}
        self.wfile.write (method(query_components).encode())
        
        return
    
def startServer(host='', port=8080):
    global HOST_URL
    try:
        # Create a web server and define the handler to manage the incoming request
        server = HTTPServer(('', port), OTPserver)
        HOST_URL = 'http://%s:%4d'  % (host,port)
        print ('Started httpserver: ' + HOST_URL )
    
        #Wait forever for incoming htto requests
        server.serve_forever()
    
    except KeyboardInterrupt:
        print ('^C received, shutting down the web server' )
        server.socket.close()
    
# Module test code
def selfTest():
    print( "generateSecret=%s" % generateSecret())
    print( "currentHOTP=%s" % currentHOTP())
    print( "currentTOTP=%s" % currentTOTP())
    
    secret = generateSecret()
    name = 'alice'
    registerUser({'name':name,'secret':secret})
    topt = currentTOTP(name)
    hopt = currentHOTP(name)
    print("Registered %s, secret= %s, topt= %s, hopt=%s" % (name, secret, topt, hopt))

    print("Validate topt= %s" % validateTOTP({'name':'alice','code':topt}))
    print("Validate hopt= %s" % validateHOTP({'name':'alice','code':hopt}))

    # errors
    rolloverTOTP()
    print("Validate old topt= %s (should fail)" % validateHOTP({'name':'alice','code':topt}))
    hopt = get_otp_token(SECRETS.get(name,'unknown'), HOTP_COUNTER+20)
    print("Invalid hopt=1 %s (should fail)" % validateHOTP({'name':'alice','code':1}))
    print("Validate hopt=+20 %s (should fail)" % validateHOTP({'name':'alice','code':hopt}))

    
# Running as a program starts a server, user secrets do NOT persist
if __name__ == "__main__":
    HOST = socket.gethostbyname(socket.gethostname())
    PORT = 80
    startServer( HOST, PORT)
