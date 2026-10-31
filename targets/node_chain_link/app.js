// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// Deliberately vulnerable local fixture. Run only through DockerSandboxManager.
const http = require('http');
const url = require('url');

const ACCOUNTS = [
    { id: 101, username: 'alice', role: 'user' },
    { id: 102, username: 'bob', role: 'admin' }
];

// Link A: logic-abuse gate. The role query parameter is accepted from input;
// a magic grant value ('grant:reviewer') silently escalates the effective
// role to reviewer. Without the grant the effective role stays unprivileged,
// so the dynamic-expression sink below refuses to evaluate (looks guarded).
const PRIVILEGED_GRANT = 'grant:reviewer';

const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url, true);
    if (parsedUrl.pathname === '/lookup' && req.method === 'GET') {
        const rawUserId = parsedUrl.query.id || '';
        const rawRole = parsedUrl.query.role || 'viewer';
        const rawGrant = parsedUrl.query.grant || '';
        const effectiveRole = rawGrant === PRIVILEGED_GRANT ? 'reviewer' : 'viewer';
        // Link B: dynamic-expression sink, reachable only through the role
        // Link A grants. Unprivileged roles are rejected before evaluation
        // (single-step probe exits 1); the granted reviewer role falls into
        // the unguarded expression (chained probe exits 0).
        if (effectiveRole !== 'reviewer') {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'error', detail: 'Insufficient role' }));
            return;
        }
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
    console.log('Secure Mitigation System fixture listening on port 8080');
});
