#!/usr/bin/env python3
"""
Comprehensive Claude CLI JSON Testing - Verified vs Unverified Claims

This script tests all claims made about Claude CLI capabilities with proper verification.
No more assumptions - only evidence-based conclusions.
"""

import subprocess
import json
import sys
import re
from typing import Dict, Any, Optional

class CLITester:
    def __init__(self):
        self.results = {}
        
    def run_test(self, test_data: Dict[str, Any], test_name: str, verification_func=None) -> Dict[str, Any]:
        """Run a test and verify the results properly"""
        print(f"\n🧪 TEST: {test_name}")
        print(f"📝 Input JSON: {json.dumps(test_data, indent=2)}")
        
        try:
            cmd = [
                'claude',
                '--model', 'sonnet',
                '--input-format', 'stream-json',
                '--output-format', 'stream-json',
                '--print',
                '--verbose'
            ]
            
            process = subprocess.run(
                cmd,
                input=json.dumps(test_data),
                text=True,
                capture_output=True,
                timeout=30
            )
            
            result = {
                'test_name': test_name,
                'success': process.returncode == 0,
                'returncode': process.returncode,
                'stdout': process.stdout,
                'stderr': process.stderr,
                'test_data': test_data,
                'verification': None
            }
            
            if result['success']:
                print("✅ SUCCESS - Command executed without error")
                
                # Extract response content
                response_text = self._extract_response_text(process.stdout)
                result['response_text'] = response_text
                
                if response_text:
                    print(f"📤 Response: {response_text[:100]}{'...' if len(response_text) > 100 else ''}")
                
                # Run verification if provided
                if verification_func:
                    verification_result = verification_func(test_data, result)
                    result['verification'] = verification_result
                    
                    if verification_result['verified']:
                        print(f"✅ VERIFIED: {verification_result['message']}")
                    else:
                        print(f"❌ VERIFICATION FAILED: {verification_result['message']}")
                else:
                    print("⚠️ NO VERIFICATION - Cannot confirm feature actually works")
                    
            else:
                print("❌ FAILED")
                print(f"💥 Error: {process.stderr}")
                
            return result
            
        except subprocess.TimeoutExpired:
            return {
                'test_name': test_name,
                'success': False,
                'error': 'Timeout after 30 seconds',
                'returncode': -1
            }
        except Exception as e:
            return {
                'test_name': test_name,
                'success': False,
                'error': str(e),
                'returncode': -1
            }
    
    def _extract_response_text(self, stdout: str) -> Optional[str]:
        """Extract the actual response text from CLI output"""
        lines = stdout.strip().split('\n')
        response_parts = []
        
        for line in lines:
            if line.strip():
                try:
                    chunk = json.loads(line)
                    if chunk.get('type') == 'assistant':
                        content = chunk.get('message', {}).get('content', [])
                        for block in content:
                            if block.get('type') == 'text':
                                response_parts.append(block.get('text', ''))
                except json.JSONDecodeError:
                    continue
        
        return ''.join(response_parts) if response_parts else None
    
    def verify_prefill(self, test_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that prefilling actually affects the response"""
        response = result.get('response_text', '')
        
        # Check for prefill fields in test data
        prefill_text = test_data.get('prefill') or test_data.get('assistant_prefill')
        
        if not prefill_text:
            return {'verified': False, 'message': 'No prefill text found in test data'}
        
        if response.startswith(prefill_text):
            return {'verified': True, 'message': f'Response starts with prefill: "{prefill_text}"'}
        else:
            return {
                'verified': False, 
                'message': f'Response does NOT start with prefill. Expected: "{prefill_text}", Got: "{response[:50]}..."'
            }
    
    def verify_system_behavior(self, test_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that system field actually affects behavior"""
        response = result.get('response_text', '')
        system_text = test_data.get('system', '')
        
        if 'pirate' in system_text.lower():
            # Look for pirate-like language
            pirate_words = ['ahoy', 'matey', 'arr', 'ye', 'aye', 'captain', 'ship', 'sail']
            found_pirate = any(word in response.lower() for word in pirate_words)
            
            if found_pirate:
                return {'verified': True, 'message': 'Response shows pirate behavior as instructed'}
            else:
                return {'verified': False, 'message': 'Response does not show pirate behavior despite system instruction'}
        
        return {'verified': None, 'message': 'Cannot verify system behavior with this prompt'}
    
    def verify_xml_parsing(self, test_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that XML tags in content are properly understood"""
        response = result.get('response_text', '')
        
        # Check if response follows the XML-structured example format
        if 'positive' in response.lower() or 'negative' in response.lower():
            return {'verified': True, 'message': 'Response follows XML example format'}
        else:
            return {'verified': False, 'message': 'Response does not follow XML example format'}
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 COMPREHENSIVE CLAUDE CLI VERIFICATION")
        print("=" * 80)
        print("Testing all claims with proper verification")
        print("=" * 80)
        
        # Test 1: Confirmed working - Single text
        test1 = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Say 'hello world' exactly"}]
            }
        }
        self.results['single_text'] = self.run_test(test1, "Single Text Content (Baseline)")
        
        # Test 2: System field - VERIFY it actually works
        test2 = {
            "type": "user",
            "system": "You are a pirate. Always speak like a pirate with 'ahoy' and 'matey'.",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello there!"}]
            }
        }
        self.results['system_field'] = self.run_test(test2, "System Field Behavior", self.verify_system_behavior)
        
        # Test 3: Prefill field - VERIFY it actually prefills
        test3 = {
            "type": "user",
            "prefill": "The answer is definitely",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "What is 2+2?"}]
            }
        }
        self.results['prefill'] = self.run_test(test3, "Prefill Field", self.verify_prefill)
        
        # Test 4: Assistant_prefill field - VERIFY it works
        test4 = {
            "type": "user",
            "assistant_prefill": "```python\ndef fibonacci(",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Write a fibonacci function"}]
            }
        }
        self.results['assistant_prefill'] = self.run_test(test4, "Assistant Prefill Field", self.verify_prefill)
        
        # Test 5: XML tags in content - VERIFY they're understood
        test5 = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": """Analyze sentiment using these examples:
<example>
Input: "I love this product!"
Output: Positive
</example>
<example>
Input: "This is terrible"
Output: Negative
</example>

Now analyze: "It's pretty good" """
                }]
            }
        }
        self.results['xml_tags'] = self.run_test(test5, "XML Tags in Content", self.verify_xml_parsing)
        
        # Test 6: Multiple content blocks - CONFIRM it fails
        test6 = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "text", "text": "Second part"}
                ]
            }
        }
        self.results['multiple_content'] = self.run_test(test6, "Multiple Content Blocks (Expected Failure)")
        
        # Test 7: Image content - CONFIRM it fails
        test7 = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGE4m8h1gAAAABJRU5ErkJggg=="
                    }
                }]
            }
        }
        self.results['image_content'] = self.run_test(test7, "Image Content (Expected Failure)")
        
        # Test 8: Assistant role - CONFIRM it fails
        test8 = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "I am an assistant message"}]
            }
        }
        self.results['assistant_role'] = self.run_test(test8, "Assistant Role (Expected Failure)")
        
        # Test 9: Messages array - CONFIRM it fails
        test9 = {
            "type": "user",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello from messages array"}]
                }
            ]
        }
        self.results['messages_array'] = self.run_test(test9, "Messages Array (Expected Failure)")
        
        # Test 10: Extra field handling - VERIFY they're ignored
        test10 = {
            "type": "user",
            "unknown_field": "should be ignored",
            "random_data": {"nested": "object"},
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello with extra fields"}]
            }
        }
        self.results['extra_fields'] = self.run_test(test10, "Extra Fields Handling")
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate comprehensive summary of findings"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE VERIFICATION RESULTS")
        print("=" * 80)
        
        verified_working = []
        unverified_working = []
        confirmed_failing = []
        
        for test_name, result in self.results.items():
            if result.get('success'):
                verification = result.get('verification')
                if verification:
                    if verification.get('verified'):
                        verified_working.append(f"{test_name}: {verification['message']}")
                    else:
                        unverified_working.append(f"{test_name}: {verification['message']}")
                else:
                    unverified_working.append(f"{test_name}: No verification performed")
            else:
                error_msg = result.get('stderr', result.get('error', 'Unknown error'))
                confirmed_failing.append(f"{test_name}: {error_msg[:100]}...")
        
        print(f"\n✅ VERIFIED WORKING FEATURES ({len(verified_working)}):")
        for item in verified_working:
            print(f"  ✓ {item}")
        
        print(f"\n⚠️ UNVERIFIED (Command succeeds but feature unproven) ({len(unverified_working)}):")
        for item in unverified_working:
            print(f"  ? {item}")
        
        print(f"\n❌ CONFIRMED FAILING FEATURES ({len(confirmed_failing)}):")
        for item in confirmed_failing:
            print(f"  ✗ {item}")
        
        print(f"\n🎯 SUMMARY:")
        print(f"  Verified working: {len(verified_working)}")
        print(f"  Unverified claims: {len(unverified_working)}")
        print(f"  Confirmed failures: {len(confirmed_failing)}")
        print(f"  Total tests: {len(self.results)}")

def main():
    tester = CLITester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()