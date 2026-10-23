#!/bin/sh
# Does the public routing server avoid tolls? Sydney CBD -> Macquarie Park (M2 / Lane Cove Tunnel are tolled), and Melbourne CityLink.
O=https://router.project-osrm.org
for P in "151.2093,-33.8688;151.1240,-33.7760" "144.9631,-37.8136;144.8880,-37.7300"; do
  for X in "" "&exclude=toll"; do
    echo "== $P $X"
    curl -s "$O/route/v1/driving/$P?overview=false&steps=true$X" | python3 -c "
import json,sys; d=json.load(sys.stdin); print('code', d.get('code'), d.get('message',''))
r=d.get('routes',[{}])[0]; print('km', round(r.get('distance',0)/1000,1), 'min', round(r.get('duration',0)/60,1))
names=[s.get('name','')+' '+str(s.get('ref','')) for l in r.get('legs',[]) for s in l.get('steps',[])]
print('roads', [n for n in names if n.strip()][:25])
print('toll-class steps', sum(1 for l in r.get('legs',[]) for s in l.get('steps',[]) for i in s.get('intersections',[]) if 'toll' in (i.get('classes') or [])))"
  done
  curl -s "$O/table/v1/driving/$P?exclude=toll" | head -c 200; echo
done
