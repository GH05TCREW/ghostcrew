"""Tests for the Shadow Graph knowledge system."""

import pytest
import networkx as nx
from pentestagent.knowledge.graph import ShadowGraph, GraphNode, GraphEdge

class TestShadowGraph:
    """Tests for ShadowGraph class."""

    @pytest.fixture
    def graph(self):
        """Create a fresh ShadowGraph for each test."""
        return ShadowGraph()

    def test_initialization(self, graph):
        """Test graph initialization."""
        assert isinstance(graph.graph, nx.DiGraph)
        assert len(graph.graph.nodes) == 0
        assert len(graph._processed_notes) == 0

    def test_extract_host_from_note(self, graph):
        """Test extracting host IP from a note."""
        notes = {
            "scan_result": {
                "content": "Nmap scan for 192.168.1.10 shows open ports.",
                "category": "info"
            }
        }
        graph.update_from_notes(notes)
        
        assert graph.graph.has_node("host:192.168.1.10")
        node = graph.graph.nodes["host:192.168.1.10"]
        assert node["type"] == "host"
        assert node["label"] == "192.168.1.10"

    def test_extract_service_finding(self, graph):
        """Test extracting services from a finding note."""
        notes = {
            "ports_scan": {
                "content": "Found open ports: 80/tcp, 443/tcp on 10.0.0.5",
                "category": "finding"
            }
        }
        graph.update_from_notes(notes)
        
        # Check host exists
        assert graph.graph.has_node("host:10.0.0.5")
        
        # Check services exist
        assert graph.graph.has_node("service:host:10.0.0.5:80")
        assert graph.graph.has_node("service:host:10.0.0.5:443")
        
        # Check edges
        assert graph.graph.has_edge("host:10.0.0.5", "service:host:10.0.0.5:80")
        edge = graph.graph.edges["host:10.0.0.5", "service:host:10.0.0.5:80"]
        assert edge["type"] == "HAS_SERVICE"
        assert edge["protocol"] == "tcp"

    def test_extract_credential(self, graph):
        """Test extracting credentials and linking to host."""
        notes = {
            "ssh_creds": {
                "content": "Found user: admin with password 'password123' for SSH on 192.168.1.20",
                "category": "credential"
            }
        }
        graph.update_from_notes(notes)
        
        cred_id = "cred:ssh_creds"
        host_id = "host:192.168.1.20"
        
        assert graph.graph.has_node(cred_id)
        assert graph.graph.has_node(host_id)
        
        # Check edge
        assert graph.graph.has_edge(cred_id, host_id)
        edge = graph.graph.edges[cred_id, host_id]
        assert edge["type"] == "AUTH_ACCESS"
        assert edge["protocol"] == "ssh"

    def test_extract_credential_variations(self, graph):
        """Test different credential formats."""
        notes = {
            "creds_1": {
                "content": "Username: root, Password: toor",
                "category": "credential"
            },
            "creds_2": {
                "content": "Just a password: secret",
                "category": "credential"
            }
        }
        graph.update_from_notes(notes)
        
        # Check "Username: root" extraction
        node1 = graph.graph.nodes["cred:creds_1"]
        assert node1["label"] == "Creds (root)"
        
        # Check fallback for no username
        node2 = graph.graph.nodes["cred:creds_2"]
        assert node2["label"] == "Credentials"

    def test_metadata_extraction(self, graph):
        """Test extracting entities from structured metadata."""
        notes = {
            "meta_cred": {
                "content": "Some random text",
                "category": "credential",
                "metadata": {
                    "username": "admin_meta",
                    "target": "10.0.0.99",
                    "source": "10.0.0.1"
                }
            },
            "meta_vuln": {
                "content": "Bad stuff",
                "category": "vulnerability",
                "metadata": {
                    "cve": "CVE-2025-1234",
                    "target": "10.0.0.99"
                }
            }
        }
        graph.update_from_notes(notes)
        
        # Check Credential Metadata
        cred_node = graph.graph.nodes["cred:meta_cred"]
        assert cred_node["label"] == "Creds (admin_meta)"
        
        # Check Target Host
        assert graph.graph.has_node("host:10.0.0.99")
        assert graph.graph.has_edge("cred:meta_cred", "host:10.0.0.99")
        
        # Check Source Host (CONTAINS edge)
        assert graph.graph.has_node("host:10.0.0.1")
        assert graph.graph.has_edge("host:10.0.0.1", "cred:meta_cred")
        
        # Check Vulnerability Metadata
        vuln_node = graph.graph.nodes["vuln:meta_vuln"]
        assert vuln_node["label"] == "CVE-2025-1234"
        assert graph.graph.has_edge("host:10.0.0.99", "vuln:meta_vuln")

    def test_url_metadata(self, graph):
        """Test that URL metadata is added to service labels."""
        notes = {
            "web_app": {
                "content": "Admin panel found",
                "category": "finding",
                "metadata": {
                    "target": "10.0.0.5",
                    "port": "80/tcp",
                    "url": "http://10.0.0.5/admin"
                }
            }
        }
        graph.update_from_notes(notes)
        
        service_id = "service:host:10.0.0.5:80"
        assert graph.graph.has_node(service_id)
        node = graph.graph.nodes[service_id]
        assert "http://10.0.0.5/admin" in node["label"]

    def test_legacy_note_format(self, graph):
        """Test handling legacy string-only notes."""
        notes = {
            "legacy_note": "Just a simple note about 10.10.10.10"
        }
        graph.update_from_notes(notes)
        
        assert graph.graph.has_node("host:10.10.10.10")

    def test_idempotency(self, graph):
        """Test that processing the same note twice doesn't duplicate or error."""
        notes = {
            "scan": {
                "content": "Host 192.168.1.1 is up.",
                "category": "info"
            }
        }
        
        # First pass
        graph.update_from_notes(notes)
        assert len(graph.graph.nodes) == 1
        
        # Second pass
        graph.update_from_notes(notes)
        assert len(graph.graph.nodes) == 1

    def test_attack_paths(self, graph):
        """Test detection of multi-step attack paths."""
        # Manually construct a path: Cred1 -> HostA -> Cred2 -> HostB
        # 1. Cred1 gives access to HostA
        graph._add_node("cred:1", "credential", "Root Creds")
        graph._add_node("host:A", "host", "10.0.0.1")
        graph._add_edge("cred:1", "host:A", "AUTH_ACCESS")
        
        # 2. HostA has Cred2 (this edge type isn't auto-extracted yet, but logic should handle it)
        graph._add_node("cred:2", "credential", "Db Admin")
        graph._add_edge("host:A", "cred:2", "CONTAINS_CRED")
        
        # 3. Cred2 gives access to HostB
        graph._add_node("host:B", "host", "10.0.0.2")
        graph._add_edge("cred:2", "host:B", "AUTH_ACCESS")
        
        paths = graph._find_attack_paths()
        assert len(paths) == 1
        assert "Root Creds" in paths[0]
        assert "10.0.0.1" in paths[0]
        assert "Db Admin" in paths[0]
        assert "10.0.0.2" in paths[0]

    def test_mermaid_export(self, graph):
        """Test Mermaid diagram generation."""
        graph._add_node("host:1", "host", "10.0.0.1")
        graph._add_node("cred:1", "credential", "admin")
        graph._add_edge("cred:1", "host:1", "AUTH_ACCESS")
        
        mermaid = graph.to_mermaid()
        assert "graph TD" in mermaid
        assert 'host_1["🖥️ 10.0.0.1"]' in mermaid
        assert 'cred_1["🔑 admin"]' in mermaid
        assert "cred_1 -->|AUTH_ACCESS| host_1" in mermaid

    def test_multiple_ips_in_one_note(self, graph):
        """Test a single note referencing multiple hosts."""
        notes = {
            "subnet_scan": {
                "content": "Scanning 192.168.1.1, 192.168.1.2, and 192.168.1.3",
                "category": "info"
            }
        }
        graph.update_from_notes(notes)
        
        assert graph.graph.has_node("host:192.168.1.1")
        assert graph.graph.has_node("host:192.168.1.2")
        assert graph.graph.has_node("host:192.168.1.3")
