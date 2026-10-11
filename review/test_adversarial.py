"""Independent protocol histories; isolated process, temporary database, ephemeral HTTP."""
import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from base import Problem, handler
from service import Service

class Review(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.database=Path(self.temp.name)/'state.sqlite'
  self.a=Service(self.database);self.b=Service(self.database);self.servers=[]
 def tearDown(self):
  for server,thread in self.servers:server.shutdown();server.server_close();thread.join(2)
  self.temp.cleanup()
 def body(self,action,args=None,identity=None):return {'id':identity or str(uuid.uuid4()),'action':action,'args':args or {}}
 def run_command(self,body,owner=None):return (owner or self.a).route('POST','/commands',body)[1]
 def command(self,action,args=None,owner=None):return self.run_command(self.body(action,args),owner)
 def view(self,owner=None):return (owner or self.a).route('GET','/view',{})[1]['data']
 def serve(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.a));thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True);thread.start();self.servers.append((server,thread));return server.server_port
 def http(self,port,path,body=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=4)
  try:
   c.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body));r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()

 def grant(self,row=None):
  r=row or self.view()['room'];return {'roomId':r['id'],'incarnation':r['incarnation'],'generation':r['generation']}
 def joined(self):self.command('start');self.command('accept',self.grant());return self.grant()
 def test_join_is_not_connected_and_new_generation_fences_ready_and_disconnect(self):
  old=self.joined();self.assertEqual('CONNECTING',self.view()['room']['transport'])
  self.command('reconnect',old);new=self.grant();self.assertEqual(2,new['generation'])
  for action in ('ready','disconnect','mute'):
   args=old|({'muted':True} if action=='mute' else {})
   self.assertFalse(self.command(action,args)['outcome']['accepted'])
  self.assertEqual('CONNECTING',self.view()['room']['transport'])
  self.command('ready',new);self.assertEqual('CONNECTED',self.view()['room']['transport'])
 def test_end_is_terminal_even_for_matching_grant(self):
  grant=self.joined();self.command('end',grant)
  for action in ('ready','disconnect','reconnect','accept','end','mute'):
   self.assertFalse(self.command(action,grant|({'muted':True} if action=='mute' else {}))['outcome']['accepted'])
  r=self.view()['room'];self.assertEqual(('ENDED','CLOSED'),(r['phase'],r['transport']))
 def test_new_room_and_incarnation_fence_old_call(self):
  old=self.joined();self.command('end',old);self.command('start');new=self.grant()
  self.assertNotEqual(old['roomId'],new['roomId']);self.assertEqual(old['incarnation']+1,new['incarnation'])
  for action in ('accept','ready','end'):self.assertFalse(self.command(action,old)['outcome']['accepted'])
  self.assertEqual('RINGING',self.view()['room']['phase'])
 def test_target_mute_repetition_is_not_toggle(self):
  grant=self.joined();body=self.body('mute',grant|{'muted':True})
  first=self.run_command(body);self.assertEqual(first,self.run_command(body,self.b))
  self.command('mute',grant|{'muted':True});self.assertTrue(self.view()['room']['muted'])
  self.command('mute',grant|{'muted':False});self.assertFalse(self.view()['room']['muted'])
 def test_two_service_reconnects_admit_one_generation_increment(self):
  grant=self.joined()
  with concurrent.futures.ThreadPoolExecutor(2) as pool:
   outcomes=list(pool.map(lambda owner:self.command('reconnect',grant,owner)['outcome']['accepted'],[self.a,self.b]))
  self.assertEqual([False,True],sorted(outcomes));self.assertEqual(2,self.view()['room']['generation'])
 def test_prejoin_ready_rejection_remains_historical_after_acceptance(self):
  self.command('start');grant=self.grant();early=self.body('ready',grant)
  rejection=self.run_command(early);self.assertFalse(rejection['outcome']['accepted'])
  self.command('accept',grant);self.assertEqual(rejection,self.run_command(early,self.b))
  self.assertEqual('CONNECTING',self.view()['room']['transport']);self.command('ready',grant)
  self.assertEqual('CONNECTED',self.view()['room']['transport'])
 def test_lost_accept_reply_replays_after_restart_and_does_not_undo_end(self):
  self.command('start');grant=self.grant();body=self.body('accept',grant);port=self.serve()
  self.http(port,'/__control',{'drop_reply':True})
  with self.assertRaises(http.client.RemoteDisconnected):self.http(port,'/commands',body)
  self.http(port,'/__control',{});reconstructed=Service(self.database)
  receipt=self.run_command(body,reconstructed);self.assertEqual('JOINED',receipt['data']['room']['phase'])
  self.command('end',grant);self.assertEqual(receipt,self.run_command(body,reconstructed))
  self.assertEqual('ENDED',self.view()['room']['phase'])
 def test_identity_payload_change_and_noninteger_grants_do_not_mutate(self):
  grant=self.joined();body=self.body('mute',grant|{'muted':True});self.run_command(body)
  with self.assertRaises(Problem):self.run_command(body|{'args':grant|{'muted':False}})
  before=self.view()
  for bad in (True,1.0,'1'):
   with self.assertRaises(Problem):self.command('ready',grant|{'generation':bad})
  self.assertEqual(before,self.view())
 def test_active_room_refuses_replacement_and_historical_start_is_not_current(self):
  body=self.body('start');first=self.run_command(body)
  self.assertFalse(self.command('start')['outcome']['accepted'])
  self.command('end',self.grant());self.command('start')
  self.assertEqual(first,self.run_command(body));self.assertNotEqual(first['data']['room']['id'],self.view()['room']['id'])

if __name__=='__main__':unittest.main()
