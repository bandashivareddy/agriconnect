const fs=require('fs'), {parse}=require('@babel/parser');
const files=['App','AuthPage','Onboarding','FarmSetup','CropManagement','FarmLedger','CropInputs','CropHarvests','ProductionLifecycle','TaskServices','BookingForm','MyBookings'];
const keys=new Set(Object.keys(JSON.parse(fs.readFileSync('src/locales/en.json','utf8'))));
const remaining=[];
for(const name of files) {
 const source=fs.readFileSync(`src/${name}.jsx`,'utf8'), ast=parse(source,{sourceType:'module',plugins:['jsx']});
 function walk(n) {if(!n||typeof n!=='object')return;
  if(n.type==='CallExpression'&&n.callee.name==='t'&&n.arguments[0]?.type==='StringLiteral')keys.add(n.arguments[0].value);
  if(n.type==='ObjectProperty'&&n.key.name==='key'&&n.value.type==='StringLiteral'&&/[A-Z ]/.test(n.value.value))keys.add(n.value.value);
  if(n.type==='JSXText'&&/[A-Za-z]{2}/.test(n.value))remaining.push(`${name}:${n.loc.start.line} ${n.value.trim()}`);
  for(const [k,v] of Object.entries(n))if(!['loc','extra'].includes(k)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}
 } walk(ast);
}
fs.writeFileSync('src/locales/en.json',JSON.stringify(Object.fromEntries([...keys].sort().map(k=>[k,k])),null,2)+'\n');
fs.writeFileSync('ux2-remaining.txt',remaining.join('\n'));
console.log(`${keys.size} keys; ${remaining.length} remaining JSX texts`);
