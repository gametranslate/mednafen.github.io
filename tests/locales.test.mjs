import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('all ten locale bundles have complete messages and intact placeholders',()=>{
 const read=lang=>JSON.parse(readFileSync(new URL(`../src/locales/${lang}.json`,import.meta.url),'utf8'));
 const en=read('en');
 for(const lang of ['en','de','vi','fr','es','it','ko','zh-TW','zh-CN','ja']){
  const data=read(lang);
  assert.deepEqual(Object.keys(data).sort(),Object.keys(en).sort(),lang);
  for(const [key,value] of Object.entries(data)){
   assert.ok(value.trim(),`${lang}: ${key}`);
   assert.deepEqual((value.match(/\{\d+\}/g)??[]).sort(),(key.match(/\{\d+\}/g)??[]).sort(),`${lang}: ${key}`);
  }
 }
 assert.equal(en['Thêm game'],'Add games');
 assert.equal(en['Kho game của bạn'],'Your library');
});
