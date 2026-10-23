import {chromium} from '/opt/node-tools/node_modules/playwright/index.mjs';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium',proxy:{server:process.env.HTTPS_PROXY},args:['--ignore-certificate-errors']});
const p=await b.newPage();p.on('requestfailed',r=>console.log('fail',r.url().slice(0,60),r.failure().errorText));
const r=await p.goto('https://gfx.nrk.no/xDSKYBqJzKqOBFHBs6lXDgiBe7Vr_gSnaZvy-XcQfE6Q.jpg').catch(e=>console.log(e.message));console.log(r&&r.status());await b.close();
