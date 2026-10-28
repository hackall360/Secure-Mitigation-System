// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// Deliberately vulnerable local fixture. Run only through DockerSandboxManager.
const http = require('http');
const url = require('url');

const ACCOUNTS = [
    { id: 101, username: 'alice', role: 'user' },
    { id: 102, username: 'bob', role: 'admin' }
];

const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url, true);
    if (parsedUrl.pathname === '/lookup' && req.method === 'GET') {
        const rawUserId = parsedUrl.query.id || '';
        const queryExpression = ` item.id == ${rawUserId} `;
        try {
            const filterFn = new Function('item', `return (${queryExpression});`);
            const matches = ACCOUNTS.filter(filterFn);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', count: matches.length, results: matches }));
        } catch (err) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'error', detail: err.message }));
        }
        return;
    }
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'not_found' }));
});

server.listen(8080, '0.0.0.0', () => {
    console.log('PurpleBox fixture listening on port 8080');
});
