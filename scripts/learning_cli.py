#!/usr/bin/env python3
"""
Archy Learning System CLI
Manage the AI's memory and learning
"""
import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path(__file__).parent))

from bias_manager import BiasManager
from memory_manager import MemoryManager
from brain_orchestrator import BrainOrchestrator


def cmd_stats(args):
    """Show system statistics."""
    memory = MemoryManager()
    brain = BrainOrchestrator()
    
    print("\n📊 Learning System Statistics")
    print("="*60)
    
    mem_stats = memory.get_memory_stats()
    print(f"\n💾 Memory:")
    print(f"  Staging:")
    print(f"    • Unpromoted: {mem_stats['staging']['unpromoted']}")
    print(f"    • Promoted:   {mem_stats['staging']['promoted']}")
    print(f"    • Total:      {mem_stats['staging']['total']}")
    print(f"  Validated:")
    print(f"    • Active:     {mem_stats['validated']['active']}")
    print(f"    • Retired:    {mem_stats['validated']['retired']}")
    print(f"    • Total:      {mem_stats['validated']['total']}")
    
    cache_stats = brain.get_cache_stats()
    print(f"\n🧠 Neural Cache:")
    print(f"  • Cached embeddings: {cache_stats['cached_embeddings']}")
    print(f"  • Cache size:        {cache_stats['cache_size_bytes']:,} bytes")
    
    print()


def cmd_list_staged(args):
    """List staged experiences."""
    memory = MemoryManager()
    staged = memory.list_staged(limit=args.limit, unpromoted_only=not args.all)
    
    print(f"\n📝 Staged Experiences ({len(staged)})")
    print("="*60)
    
    for item in staged:
        status = "✓ Promoted" if item['promoted'] else "⏳ Pending"
        print(f"\nID {item['id']} [{status}]")
        print(f"  Role: {item['role']}")
        print(f"  Content: {item['content'][:100]}...")
        
        if item['validator_result']:
            vr = item['validator_result']
            print(f"  Score: {vr['score']:.3f} - {vr['verdict']}")


def cmd_list_memories(args):
    """List validated memories."""
    memory = MemoryManager()
    memories = memory.list_memories(limit=args.limit, include_retired=args.all)
    
    print(f"\n💾 Validated Memories ({len(memories)})")
    print("="*60)
    
    for mem in memories:
        status = "🗑️  Retired" if mem['retired'] else "✅ Active"
        print(f"\nID {mem['id']} [{status}]")
        print(f"  Content: {mem['content'][:100]}...")
        if 'validator' in mem['meta']:
            print(f"  Score: {mem['meta']['validator']['score']:.3f}")


def cmd_promote(args):
    """Validate and promote staged items."""
    memory = MemoryManager()
    
    if args.batch:
        print(f"\n🔄 Batch processing up to {args.limit} items...")
        stats = memory.batch_validate_and_promote(limit=args.limit)
        
        print(f"\n📊 Results:")
        print(f"  • Processed:    {stats['processed']}")
        print(f"  • Promoted:     {stats['promoted']}")
        print(f"  • Rejected:     {stats['rejected']}")
        print(f"  • Needs review: {stats['needs_review']}")
    else:
        print(f"\n🔍 Validating staging ID {args.id}...")
        result = memory.validate_and_promote(args.id, admin_approve=args.force)
        
        print(f"\n📊 Result: {result['status']}")
        if 'validator' in result:
            v = result['validator']
            print(f"  Score: {v['score']:.3f}")
            print(f"  Verdict: {v['verdict']}")
            if v['safety_issues']:
                print(f"  ⚠️  Safety issues: {v['safety_issues']}")


def cmd_search(args):
    """Search similar memories."""
    memory = MemoryManager()
    brain = BrainOrchestrator()
    
    print(f"\n🔍 Searching for: '{args.query}'")
    print("="*60)
    
    memories = memory.list_memories(limit=500)
    if not memories:
        print("\n⚠️  No validated memories yet.")
        return
    
    memory_texts = [m['content'] for m in memories]
    similar = brain.find_similar(args.query, memory_texts, top_k=args.top_k)
    
    print(f"\nTop {len(similar)} similar memories:\n")
    for i, result in enumerate(similar, 1):
        mem_id = memories[result['index']]['id']
        print(f"{i}. [Score: {result['score']:.3f}] (ID {mem_id})")
        print(f"   {result['text'][:150]}...")
        print()


def cmd_retire(args):
    """Retire a memory."""
    memory = MemoryManager()
    
    print(f"\n🗑️  Retiring memory ID {args.id}...")
    success = memory.retire_memory(args.id, reason=args.reason or "Manual retirement")
    
    if success:
        print("✅ Memory retired successfully")
    else:
        print("❌ Failed to retire memory (not found?)")


def cmd_clear_cache(args):
    """Clear embedding cache."""
    brain = BrainOrchestrator()
    
    if not args.confirm:
        print("⚠️  This will clear all cached embeddings.")
        print("   Run with --confirm to proceed.")
        return
    
    brain.clear_cache()
    print("✅ Embedding cache cleared")


def cmd_bias(args):
    """Show or update bias settings."""
    bias = BiasManager()
    
    if args.set:
        key, value = args.set.split('=')
        try:
            value = float(value)
        except ValueError:
            pass
        
        print(f"\n🔧 Setting {key} = {value}")
        bias.update({key: value})
        print("✅ Bias updated")
    else:
        print("\n⚖️  Bias Settings")
        print("="*60)
        for key, value in bias.data.items():
            if key not in ['seen_hashes', 'forbidden_patterns', 'preferred_keywords']:
                print(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description="Archy Learning System CLI")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # stats
    parser_stats = subparsers.add_parser('stats', help='Show system statistics')
    parser_stats.set_defaults(func=cmd_stats)
    
    # list-staged
    parser_staged = subparsers.add_parser('list-staged', help='List staged experiences')
    parser_staged.add_argument('-l', '--limit', type=int, default=20, help='Max items to show')
    parser_staged.add_argument('-a', '--all', action='store_true', help='Include promoted items')
    parser_staged.set_defaults(func=cmd_list_staged)
    
    # list-memories
    parser_mem = subparsers.add_parser('list-memories', help='List validated memories')
    parser_mem.add_argument('-l', '--limit', type=int, default=20, help='Max items to show')
    parser_mem.add_argument('-a', '--all', action='store_true', help='Include retired items')
    parser_mem.set_defaults(func=cmd_list_memories)
    
    # promote
    parser_promote = subparsers.add_parser('promote', help='Validate and promote')
    parser_promote.add_argument('id', nargs='?', type=int, help='Staging ID to promote')
    parser_promote.add_argument('-b', '--batch', action='store_true', help='Batch process')
    parser_promote.add_argument('-l', '--limit', type=int, default=50, help='Batch limit')
    parser_promote.add_argument('-f', '--force', action='store_true', help='Force promotion')
    parser_promote.set_defaults(func=cmd_promote)
    
    # search
    parser_search = subparsers.add_parser('search', help='Search similar memories')
    parser_search.add_argument('query', help='Search query')
    parser_search.add_argument('-k', '--top-k', type=int, default=5, help='Number of results')
    parser_search.set_defaults(func=cmd_search)
    
    # retire
    parser_retire = subparsers.add_parser('retire', help='Retire a memory')
    parser_retire.add_argument('id', type=int, help='Memory ID to retire')
    parser_retire.add_argument('-r', '--reason', help='Retirement reason')
    parser_retire.set_defaults(func=cmd_retire)
    
    # clear-cache
    parser_cache = subparsers.add_parser('clear-cache', help='Clear embedding cache')
    parser_cache.add_argument('--confirm', action='store_true', help='Confirm action')
    parser_cache.set_defaults(func=cmd_clear_cache)
    
    # bias
    parser_bias = subparsers.add_parser('bias', help='Show/update bias settings')
    parser_bias.add_argument('--set', help='Set value (key=value)')
    parser_bias.set_defaults(func=cmd_bias)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()

