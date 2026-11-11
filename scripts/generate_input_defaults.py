"""Frontend defaults only. Leave the upstream settings catalog unchanged."""
from pathlib import Path
import json, re
ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT/'src/data/settings.json').read_text(encoding='utf-8'))
arrows = {'up':82,'down':81,'left':80,'right':79}
common = dict(arrows, a=27,b=29,x=22,y=4,start=40,select=229,run=40,
              l=20,r=26,shoulder_l=20,shoulder_r=26,ls=20,rs=26,
              button1=29,button2=27,option=40,pause=40,option_1=4,option_2=22,
              mode=229,mode_select=16,mode1=20,mode2=26,
              i=27,ii=29,iii=6,iv=4,v=22,vi=7,
              cross=29,circle=27,square=4,triangle=22,l1=20,r1=26,l2=8,r2=21,l3=6,r3=25)
values = {'command.fast_forward':'keyboard 0x0 43','fftoggle':'0',
          'command.save_state':'keyboard 0x0 58','command.load_state':'keyboard 0x0 59',
          'command.state_slot_inc':'keyboard 0x0 60','command.state_slot_dec':'keyboard 0x0 60+shift',
          'command.toggle_help':'keyboard 0x0 58+ctrl',
          'command.input_configc':'keyboard 0x0 59+ctrl',
          'command.input_configc_am':'keyboard 0x0 59+ctrl+shift',
          'command.input_config_abd':'keyboard 0x0 60+ctrl',
          'command.reinit_joysticks':'keyboard 0x0 60+ctrl+shift'}
for d in schema:
    m = re.fullmatch(r'(\w+)\.input\.(port1|builtin)\.(gamepad|gamepad2|gamepad6|dualshock|dualanalog)\.([^.]*)',d['key'])
    if not m or 'MDFNSF_CAT_INPUT_MAPPING' not in d['flags'] or m[1]=='apple2': continue
    system,_,device,button = m.groups()
    mapping = dict(common)
    if system in ('md','ss'): mapping.update(a=29,b=27,c=6,x=4,y=22,z=7)
    if system=='wswan':
        mapping.update({key+'-x':val for key,val in arrows.items()})
        mapping.update({'up-y':26,'down-y':22,'left-y':4,'right-y':7})
    if system=='vb':
        mapping.update({key+'-l':val for key,val in arrows.items()})
        mapping.update({'up-r':26,'down-r':22,'left-r':4,'right-r':7,'lt':20,'rt':8})
    if button in mapping: values[d['key']]='keyboard 0x0 '+str(mapping[button])
(ROOT/'src/data/input-defaults.json').write_text(json.dumps(dict(sorted(values.items())),indent=2)+'\n',encoding='utf-8')
print('Recommended defaults:',len(values))
