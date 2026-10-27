<?php
// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// Deliberately vulnerable local fixture. Run only through DockerSandboxManager.
header('Content-Type: application/json');
$host = $_GET['host'] ?? 'localhost';
// A deterministic local diagnostic: no external network or ping binary is needed.
$output = shell_exec("printf '%s' " . $host);
echo json_encode(['status' => 'ok', 'host' => $host, 'diagnostic' => trim($output ?? '')]);
