#!/usr/bin/env python3
"""
Test the complete learning system
"""
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bias_manager import BiasManager
from memory_manager import MemoryManager
from brain_orchestrator import BrainOrchestrator


def test_bias_manager():
    print("\n" + "="*60)
    print("TEST 1: BiasManager")
    print("="*60)
    
    bias = BiasManager(path=Path("brain/test_bias.json"))
    
    # Test scoring
    good_content = "This is a helpful explanation about how to use ls command safely"
    bad_content = "sudo rm -rf / will delete everything"
    
    good_result = bias.score_fragment(good_content)
    bad_result = bias.score_fragment(bad_content)
    
    print(f"\n✓ Good content score: {good_result['score']:.3f} - {good_result['verdict']}")
    print(f"  Breakdown: {good_result['breakdown']}")
    
    print(f"\n✗ Bad content score: {bad_result['score']:.3f} - {bad_result['verdict']}")
    print(f"  Safety issues: {bad_result['safety_issues']}")
    
    assert good_result['score'] > bad_result['score'], "Good content should score higher!"
    print("\n✅ BiasManager test PASSED")


def test_memory_manager():
    print("\n" + "="*60)
    print("TEST 2: MemoryManager (Two-Tier Learning)")
    print("="*60)
    
    bias = BiasManager(path=Path("brain/test_bias.json"))
    memory = MemoryManager(db_path=Path("brain/test_brain.db"), bias_manager=bias)
    
    # Stage some experiences
    print("\n📝 Staging experiences...")
    
    experiences = [
        ("user", "How do I list files?", {"intent": "learn"}),
        ("assistant", "Use 'ls' command to list files in current directory", {"intent": "help"}),
        ("user", "sudo rm -rf /", {"intent": "dangerous"}),
        ("assistant", "The ls -la command shows all files with details", {"intent": "explain"}),
    ]
    
    staged_ids = []
    for role, content, meta in experiences:
        sid = memory.stage_experience(role, content, meta)
        staged_ids.append(sid)
        print(f"  • Staged ID {sid}: {content[:50]}...")
    
    # Validate and promote
    print("\n🔍 Validating and promoting...")
    stats = memory.batch_validate_and_promote(limit=10)
    
    print(f"\n📊 Validation Results:")
    print(f"  • Processed: {stats['processed']}")
    print(f"  • Promoted: {stats['promoted']}")
    print(f"  • Rejected: {stats['rejected']}")
    print(f"  • Needs review: {stats['needs_review']}")
    
    # List validated memories
    memories = memory.list_memories(limit=10)
    print(f"\n💾 Validated Memories ({len(memories)}):")
    for mem in memories:
        print(f"  • ID {mem['id']}: {mem['content'][:60]}...")
        print(f"    Score: {mem['meta']['validator']['score']:.3f}")
    
    # Get stats
    stats = memory.get_memory_stats()
    print(f"\n📈 Memory Stats:")
    print(f"  Staging: {stats['staging']['unpromoted']} unpromoted, {stats['staging']['promoted']} promoted")
    print(f"  Validated: {stats['validated']['active']} active, {stats['validated']['retired']} retired")
    
    print("\n✅ MemoryManager test PASSED")


def test_brain_orchestrator():
    print("\n" + "="*60)
    print("TEST 3: BrainOrchestrator (Neural + Rust)")
    print("="*60)
    
    brain = BrainOrchestrator()
    
    # Test embeddings
    print("\n🧠 Generating embeddings...")
    texts = [
        "How to list files in Linux",
        "Show all files with details",
        "Delete everything permanently",
        "Check disk usage"
    ]
    
    embeddings = brain.embed_texts(texts, dim=128)
    
    print(f"✓ Generated {len(embeddings)} embeddings")
    for text, emb in embeddings.items():
        print(f"  • {text[:40]}... -> [{emb[0]:.4f}, {emb[1]:.4f}, ... {len(emb)} dims]")
    
    # Test similarity search
    print("\n🔍 Finding similar texts...")
    query = "how to view files"
    candidates = texts
    
    similar = brain.find_similar(query, candidates, top_k=3)
    
    print(f"\nQuery: '{query}'")
    print(f"Top {len(similar)} similar:")
    for i, result in enumerate(similar, 1):
        print(f"  {i}. [{result['score']:.3f}] {result['text']}")
    
    # Test validation
    print("\n✅ Rust validation check...")
    valid_result = brain.validate_fragment_rust("This is a normal helpful text")
    invalid_result = brain.validate_fragment_rust("rm -rf /")
    
    print(f"Valid text score: {valid_result.get('validation_score', 0):.3f}")
    print(f"Invalid text score: {invalid_result.get('validation_score', 0):.3f}")
    
    # Cache stats
    cache_stats = brain.get_cache_stats()
    print(f"\n📦 Cache stats: {cache_stats['cached_embeddings']} entries, {cache_stats['cache_size_bytes']} bytes")
    
    print("\n✅ BrainOrchestrator test PASSED")


def test_integration():
    print("\n" + "="*60)
    print("TEST 4: Full Integration (Bias + Memory + Brain)")
    print("="*60)
    
    # Initialize all components
    bias = BiasManager(path=Path("brain/test_bias.json"))
    memory = MemoryManager(db_path=Path("brain/test_brain.db"), bias_manager=bias)
    brain = BrainOrchestrator()
    
    # Simulate learning flow
    print("\n📚 Simulating learning flow...")
    
    # 1. User interaction
    user_query = "How do I check my disk space?"
    print(f"\n1. User query: '{user_query}'")
    
    # 2. Stage the query
    query_id = memory.stage_experience("user", user_query, {"intent": "learn", "topic": "system"})
    print(f"   → Staged as ID {query_id}")
    
    # 3. Generate response
    response = "Use 'df -h' to see disk usage in human-readable format, or 'du -sh *' for directory sizes."
    response_id = memory.stage_experience("assistant", response, {"intent": "help", "topic": "system"})
    print(f"   → Response staged as ID {response_id}")
    
    # 4. Validate and possibly promote
    result = memory.validate_and_promote(query_id)
    print(f"\n2. Validation result: {result['status']}")
    if result['status'] == 'promoted':
        print(f"   ✓ Promoted to memory ID {result['memory_id']}")
        print(f"   Score: {result['validator']['score']:.3f}")
    
    result = memory.validate_and_promote(response_id)
    print(f"\n3. Response validation: {result['status']}")
    if result['status'] == 'promoted':
        print(f"   ✓ Promoted to memory ID {result['memory_id']}")
    
    # 5. Use embeddings to find similar past memories
    print("\n4. Finding similar past experiences...")
    memories = memory.list_memories(limit=50)
    memory_texts = [m['content'] for m in memories]
    
    if memory_texts:
        similar = brain.find_similar(user_query, memory_texts, top_k=3)
        print(f"   Found {len(similar)} similar memories:")
        for s in similar:
            print(f"   • [{s['score']:.3f}] {s['text'][:60]}...")
    
    print("\n✅ Full integration test PASSED")
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("="*60)


if __name__ == "__main__":
    try:
        test_bias_manager()
        test_memory_manager()
        test_brain_orchestrator()
        test_integration()
        
        print("\n✨ Learning system is ready!")
        print("\nNext steps:")
        print("  1. Integrate with archy_chat.py")
        print("  2. Add neural network training (PyTorch/TensorFlow)")
        print("  3. Implement continuous learning loop")
        print("  4. Add admin review dashboard")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

