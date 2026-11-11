import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {effectiveValue,validateSetting} from '../src/settings-utils.mjs';
const read=name=>JSON.parse(readFileSync(new URL('../src/data/'+name,import.meta.url),'utf8'));
const schema=new Map(read('settings.json').map(d=>[d.key,d]));
const defaults=read('input-defaults.json');
test('recommended keys reserve Tab and F1-F3 without changing custom mappings',()=>{
 for(const [key,value] of Object.entries(defaults)){
  assert.ok(schema.has(key),key);assert.equal(validateSetting(schema.get(key),value),'',key);
  if(key.includes('.input.'))assert.ok(!/keyboard 0x0 (?:8[9]|9\d)(?:\D|$)/.test(value),key);
 }
 for(const [key,value] of Object.entries({'command.fast_forward':'43','command.save_state':'58','command.load_state':'59','command.state_slot_inc':'60','command.state_slot_dec':'60+shift'}))assert.equal(defaults[key],'keyboard 0x0 '+value);
 for(const code of [43,58,59,60]){
  const bound=[...schema.values()].filter(d=>d.key.startsWith('command.')&&(defaults[d.key]??d.default)==='keyboard 0x0 '+code);
  assert.equal(bound.length,1,'Conflicting shortcut '+code);
 }
 const d={...schema.get('wswan.input.builtin.gamepad.a'),default:defaults['wswan.input.builtin.gamepad.a']};
 assert.equal(effectiveValue(d,{},{}),'keyboard 0x0 27');
 assert.equal(effectiveValue(d,{}, {[d.key]:'joystick custom'}),'joystick custom');
 assert.equal(effectiveValue(d,{[d.key]:''},{}),'');
 assert.equal(defaults['snes.input.port1.gamepad.select'],'keyboard 0x0 229');
});
