#!/usr/bin/env python3
"""
🚀 Semantic Versioning Script for Bugra-Bot

Automatically bumps version based on conventional commits and generates changelog.

Usage:
    python scripts/version-bump.py [major|minor|patch|auto]
    
    major - Breaking changes (X.0.0)
    minor - New features (x.X.0)  
    patch - Bug fixes (x.x.X)
    auto  - Detect from commits (default)
"""

import subprocess
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional


class VersionBumper:
    """Semantic versioning manager"""
    
    VERSION_TYPES = ['major', 'minor', 'patch']
    
    def __init__(self, version_file: str = "src/bot/config.py"):
        self.version_file = Path(version_file)
        self.current_version = self._get_current_version()
        
    def _get_current_version(self) -> str:
        """Extract current version from git tags or config file"""
        try:
            # Get latest tag from git
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                tag = result.stdout.strip()
                # Remove 'v' prefix if present
                if tag.startswith('v'):
                    tag = tag[1:]
                return tag
        except:
            pass
        
        # Fallback to config file
        if not self.version_file.exists():
            return "3.0.0"
            
        content = self.version_file.read_text(encoding='utf-8')
        match = re.search(r'VERSION\s*=\s*["\']([\d.]+)["\']', content)
        return match.group(1) if match else "3.0.0"
    
    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse version string to tuple"""
        parts = version.split('.')
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    
    def _bump_version(self, bump_type: str) -> str:
        """Bump version based on type"""
        major, minor, patch = self._parse_version(self.current_version)
        
        if bump_type == 'major':
            return f"{major + 1}.0.0"
        elif bump_type == 'minor':
            return f"{major}.{minor + 1}.0"
        else:  # patch
            return f"{major}.{minor}.{patch + 1}"
    
    def _get_commits_since_last_tag(self) -> List[Tuple[str, str]]:
        """Get commits since last version tag"""
        try:
            # Get last tag
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                capture_output=True, text=True
            )
            last_tag = result.stdout.strip() if result.returncode == 0 else None
            
            # Get commits since last tag
            if last_tag:
                cmd = ['git', 'log', f'{last_tag}..HEAD', '--pretty=format:%s|%b<END>']
            else:
                cmd = ['git', 'log', '--pretty=format:%s|%b<END>']
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            commits = result.stdout.split('<END>')
            
            parsed = []
            for commit in commits:
                if '|' in commit:
                    subject, body = commit.split('|', 1)
                    parsed.append((subject.strip(), body.strip()))
                elif commit.strip():
                    parsed.append((commit.strip(), ''))
                    
            return parsed
            
        except Exception as e:
            print(f"⚠️  Could not get commits: {e}")
            return []
    
    def _detect_bump_type(self, commits: List[Tuple[str, str]]) -> str:
        """Detect bump type from commits"""
        has_breaking = False
        has_feat = False
        has_fix = False
        
        for subject, body in commits:
            # Check for breaking changes
            if 'BREAKING CHANGE' in body or '!' in subject.split(':')[0] if ':' in subject else False:
                has_breaking = True
                break
            # Check for features
            elif subject.startswith('feat'):
                has_feat = True
            # Check for fixes
            elif subject.startswith('fix'):
                has_fix = True
        
        if has_breaking:
            return 'major'
        elif has_feat:
            return 'minor'
        elif has_fix:
            return 'patch'
        else:
            return 'patch'  # Default to patch
    
    def _generate_changelog_entry(self, commits: List[Tuple[str, str]], version: str) -> str:
        """Generate changelog entry"""
        categories = {
            'feat': [],
            'fix': [],
            'docs': [],
            'style': [],
            'refactor': [],
            'perf': [],
            'test': [],
            'build': [],
            'ci': [],
            'chore': []
        }
        
        for subject, body in commits:
            if ':' in subject:
                type_part = subject.split(':')[0]
                # Remove scope if present
                commit_type = type_part.split('(')[0] if '(' in type_part else type_part
                message = subject.split(':', 1)[1].strip()
                
                if commit_type in categories:
                    categories[commit_type].append(message)
        
        # Build changelog
        lines = [
            f"## [{version}] - {datetime.now().strftime('%Y-%m-%d')}",
            ""
        ]
        
        category_names = {
            'feat': '✨ Features',
            'fix': '🐛 Bug Fixes',
            'docs': '📚 Documentation',
            'style': '💄 Styles',
            'refactor': '♻️ Code Refactoring',
            'perf': '⚡ Performance',
            'test': '✅ Tests',
            'build': '📦 Build System',
            'ci': '🔧 CI/CD',
            'chore': '🏠 Chores'
        }
        
        for commit_type, messages in categories.items():
            if messages:
                lines.append(f"### {category_names.get(commit_type, commit_type)}")
                for msg in messages:
                    lines.append(f"- {msg}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _update_version_file(self, new_version: str):
        """Update version in config file"""
        if self.version_file.exists():
            content = self.version_file.read_text(encoding='utf-8')
            content = re.sub(
                r'VERSION\s*=\s*["\'][\d.]+["\']',
                f'VERSION = "{new_version}"',
                content
            )
            self.version_file.write_text(content, encoding='utf-8')
            print(f"✅ Updated {self.version_file} to v{new_version}")
    
    def _update_changelog(self, entry: str):
        """Update CHANGELOG.md"""
        changelog = Path("CHANGELOG.md")
        
        if changelog.exists():
            content = changelog.read_text(encoding='utf-8')
            # Insert after header
            lines = content.split('\n')
            header_end = 0
            for i, line in enumerate(lines):
                if line.startswith('# ') or line.startswith('## '):
                    header_end = i + 1
            
            new_content = '\n'.join(lines[:header_end]) + '\n\n' + entry + '\n'.join(lines[header_end:])
            changelog.write_text(new_content, encoding='utf-8')
        else:
            header = "# Changelog\n\nAll notable changes to this project will be documented here.\n\n"
            changelog.write_text(header + entry, encoding='utf-8')
        
        print(f"✅ Updated CHANGELOG.md")
    
    def bump(self, bump_type: str = 'auto') -> str:
        """Main bump process"""
        print(f"🔍 Current version: v{self.current_version}")
        
        # Get commits
        commits = self._get_commits_since_last_tag()
        if not commits:
            print("⚠️  No commits found since last tag")
            return self.current_version
        
        print(f"📋 Found {len(commits)} commits since last tag")
        
        # Detect bump type
        if bump_type == 'auto':
            bump_type = self._detect_bump_type(commits)
            print(f"🤖 Auto-detected bump type: {bump_type}")
        
        # Calculate new version
        new_version = self._bump_version(bump_type)
        print(f"🆕 New version: v{new_version}")
        
        # Generate changelog
        changelog_entry = self._generate_changelog_entry(commits, new_version)
        
        # Update files
        self._update_version_file(new_version)
        self._update_changelog(changelog_entry)
        
        # Git operations
        print("\n📝 Git operations:")
        subprocess.run(['git', 'add', '-A'])
        subprocess.run(['git', 'commit', '-m', f'chore(release): bump version to v{new_version}'])
        subprocess.run(['git', 'tag', f'v{new_version}'])
        
        print(f"\n🎉 Version bumped to v{new_version}")
        print(f"   Run 'git push origin main --tags' to publish")
        
        return new_version


def main():
    """CLI entry point"""
    bump_type = sys.argv[1] if len(sys.argv) > 1 else 'auto'
    
    if bump_type not in ['major', 'minor', 'patch', 'auto']:
        print(f"❌ Invalid bump type: {bump_type}")
        print("Usage: python scripts/version-bump.py [major|minor|patch|auto]")
        sys.exit(1)
    
    bumper = VersionBumper()
    bumper.bump(bump_type)


if __name__ == '__main__':
    main()
