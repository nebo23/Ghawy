const http = require('http');

const options = {
  hostname: '127.0.0.1',
  port: 8000,
  path: '/chat/messages?channel=general&limit=1',
  method: 'GET'
};

const req = http.request(options, res => {
  let data = '';
  res.on('data', chunk => { data += chunk; });
  res.on('end', () => {
    console.log(data);
  });
});
req.on('error', error => { console.error(error); });
req.end();
