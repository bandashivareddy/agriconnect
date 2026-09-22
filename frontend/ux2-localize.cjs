const fs = require('fs');
const { parse } = require('@babel/parser');
const files = ['App','AuthPage','Onboarding','FarmSetup','CropManagement','FarmLedger','CropInputs','CropHarvests','ProductionLifecycle','TaskServices','BookingForm','MyBookings'];
const keys = new Set(Object.keys(JSON.parse(fs.readFileSync('src/locales/en.json','utf8'))));
const messages = new Set(['error','errorMessage','message','notice','roleError','sourceError','rescheduleMessage']);
const hasWords = text => /[A-Za-z]{2}/.test(text);
const quote = JSON.stringify;
function key(text) { keys.add(text); return quote(text); }
function jsxText(value) {
  const lines = value.replace(/\r/g,'').split('\n');
  return lines.map((line,i) => { let v=line.replace(/\t/g,' '); if(i) v=v.replace(/^ +/,''); if(i<lines.length-1) v=v.replace(/ +$/,''); return v; }).filter(Boolean).join(' ');
}
for (const file of files) {
  const path = `src/${file}.jsx`, source = fs.readFileSync(path,'utf8').replace(/^\uFEFF/,'');
  const ast=parse(source,{sourceType:'module',plugins:['jsx']}); const edits=[];
  const raw=n=>source.slice(n.start,n.end);
  const edit=(a,b,text)=>edits.push({a,b,text});
  function expression(n) {
    if(!n) return '';
    if(n.type==='StringLiteral') return hasWords(n.value) ? `t(${key(n.value)})` : raw(n);
    if(n.type==='TemplateLiteral') {
      const template=n.quasis.map((q,i)=>q.value.cooked+(i<n.expressions.length?`{{v${i}}}`:'')).join('');
      if(!hasWords(template.replace(/\{\{v\d+\}\}/g,''))) return raw(n);
      return `t(${key(template)}, { ${n.expressions.map((e,i)=>`v${i}: ${expression(e)}`).join(', ')} })`;
    }
    if(n.type==='ConditionalExpression') return `${raw(n.test)} ? ${expression(n.consequent)} : ${expression(n.alternate)}`;
    if(n.type==='LogicalExpression') return `${raw(n.left)} ${n.operator} ${expression(n.right)}`;
    if(n.type==='Identifier' && messages.has(n.name)) return `messageText(${n.name})`;
    return raw(n);
  }
  function walk(n,parent) {
    if(!n || typeof n!=='object') return;
    if(n.type==='JSXText') {
      const value=jsxText(n.value); if(hasWords(value)) edit(n.start,n.end,`{t(${key(value)})}`);
    }
    if(n.type==='JSXAttribute' && ['placeholder','title','aria-label'].includes(n.name.name)) {
      if(n.value?.type==='StringLiteral' && hasWords(n.value.value)) edit(n.value.start,n.value.end,`{t(${key(n.value.value)})}`);
      else if(n.value?.type==='JSXExpressionContainer') { const out=expression(n.value.expression); if(out!==raw(n.value.expression)) edit(n.value.expression.start,n.value.expression.end,out); }
      return;
    }
    if(n.type==='JSXExpressionContainer' && parent?.type!=='JSXAttribute') {
      // Only presentation branches; comparisons, event handlers, IDs, payloads untouched.
      const containsJsx = value => value && typeof value === 'object' && (['JSXElement','JSXFragment'].includes(value.type) || Object.values(value).some(v=>Array.isArray(v)?v.some(containsJsx):containsJsx(v)));
      const out=containsJsx(n.expression) ? raw(n.expression) : expression(n.expression);
      if(out!==raw(n.expression)) { edit(n.expression.start,n.expression.end,out); return; }
    }
    if(n.type==='CallExpression' && n.callee.type==='Identifier' && /^set(Error|Message|Notice|ErrorMessage|RescheduleMessage)$/.test(n.callee.name)) {
      const arg=n.arguments[0];
      if(arg?.type==='StringLiteral' && hasWords(arg.value)) key(arg.value);
      if(arg?.type==='TemplateLiteral') {
        const template=arg.quasis.map((q,i)=>q.value.cooked+(i<arg.expressions.length?`{{v${i}}}`:'')).join('');
        edit(arg.start,arg.end,`{ key: ${key(template)}, values: { ${arg.expressions.map((e,i)=>`v${i}: ${raw(e)}`).join(', ')} } }`);
      }
    }
    if(n.type==='NewExpression' && n.callee.name==='Error' && n.arguments[0]?.type==='StringLiteral') key(n.arguments[0].value);
    // Never translate an option's implicit business value.
    if(n.type==='JSXElement' && n.openingElement.name.name==='option' && !n.openingElement.attributes.some(a=>a.name?.name==='value')) {
      const child=n.children.find(c=>c.type==='JSXExpressionContainer'||c.type==='JSXText'&&c.value.trim());
      if(child?.type==='JSXText') edit(n.openingElement.end-1,n.openingElement.end-1,` value=${quote(jsxText(child.value).trim())}`);
      if(child?.type==='JSXExpressionContainer') edit(n.openingElement.end-1,n.openingElement.end-1,` value={${raw(child.expression)}}`);
    }
    for(const [k,v] of Object.entries(n)) if(!['loc','start','end','extra','comments'].includes(k)) {
      if(Array.isArray(v)) v.forEach(x=>walk(x,n)); else if(v&&typeof v==='object') walk(v,n);
    }
  }
  walk(ast,null);
  edits.sort((a,b)=>b.a-a.a||b.b-a.b);
  let output=source,last=source.length;
  for(const e of edits) { if(e.b>last) throw Error(`Overlapping edit ${file}:${e.a}`); output=output.slice(0,e.a)+e.text+output.slice(e.b); last=e.a; }
  if(output.includes('messageText(')) output=output.replace('import { t } from "./i18n";', 'import { t, messageText } from "./i18n";');
  // Only include bindings actually used.
  if(!output.includes('messageText(')) output=output.replace('t, messageText','t');
  fs.writeFileSync(path,output);
}
fs.writeFileSync('src/locales/en.json',JSON.stringify(Object.fromEntries([...keys].sort().map(k=>[k,k])),null,2)+'\n');
console.log(`${keys.size} UI messages extracted from ${files.length} farmer/shared modules.`);
