#!/usr/bin/env python3
"""Select a native HDMI audio profile and retain an exact preference rollback."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


class Pulse:
    def command(self, *args):
        return subprocess.run(['pactl', *map(str, args)], check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

    def listing(self, kind):
        return json.loads(self.command('--format=json', 'list', kind))


def profiles(card):
    value = card.get('profiles', {})
    if isinstance(value, dict):
        return [dict(details, name=name) for name, details in value.items()]
    return value


def active_profile(card):
    value = card['active_profile']
    return value['name'] if isinstance(value, dict) else value


def choose(cards, card_name=None, profile_name=None):
    candidates = []
    for card in cards:
        if card_name and card_name not in (card['name'], str(card['index'])):
            continue
        matches = [p for p in profiles(card) if p['name'].startswith('output:hdmi')
                   and p.get('available') not in ('no', False, 0)]
        if profile_name:
            matches = [p for p in matches if p['name'] == profile_name]
        certain = [p for p in matches if p.get('available') in ('yes', True, 1)]
        if certain:
            matches = certain
        if matches:
            candidates.append((card, matches))
    if len(candidates) != 1:
        names = ', '.join(card['name'] for card, _ in candidates) or 'none'
        raise ValueError(f'Choose one available HDMI card with --card. Candidates: {names}')
    card, matches = candidates[0]
    if len(matches) > 1 and not profile_name:
        names = ', '.join(p['name'] for p in matches)
        raise ValueError(f'Multiple HDMI profiles are available; pass --profile. Choices: {names}')
    return card, matches[0]['name']


class AudioFix:
    def __init__(self, pulse=None, state=None):
        self.pulse = pulse or Pulse()
        self.state = state or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oxp3-cachy/tv-audio/state.json'

    def save(self, data):
        self.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.state.with_suffix('.tmp')
        with temporary.open('w') as stream:
            os.chmod(temporary, 0o600)
            json.dump(data, stream, indent=2)
            stream.write('\n')
        temporary.replace(self.state)

    def card(self, name):
        return next((card for card in self.pulse.listing('cards') if card['name'] == name), None)

    def wait_sink(self, predicate):
        for _ in range(50):
            matches = [sink for sink in self.pulse.listing('sinks') if predicate(sink)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError('Multiple matching sinks; choose a more specific HDMI profile')
            time.sleep(0.1)
        raise ValueError('Expected audio sink did not appear; check the connected TV and profile')

    def install(self, card_name=None, profile_name=None, move_streams=False):
        card, target = choose(self.pulse.listing('cards'), card_name, profile_name)
        if self.state.exists():
            data = json.loads(self.state.read_text())
            if data['card'] != card['name'] or data['managed_profile'] != target:
                raise ValueError('A different profile is managed already; roll it back before changing cards')
        else:
            if not active_profile(card):
                raise ValueError('Original card profile is unknown; refusing an un-restorable change')
            sinks = self.pulse.listing('sinks')
            sink_names = {str(sink['index']): sink['name'] for sink in sinks}
            data = {'version': 1, 'card': card['name'], 'previous_profile': active_profile(card),
                    'previous_default': self.pulse.command('get-default-sink'),
                    'managed_profile': target, 'managed_sink': None,
                    'streams': {str(stream['index']): sink_names.get(str(stream['sink']))
                                for stream in self.pulse.listing('sink-inputs')} if move_streams else {}}
            self.save(data)
        if move_streams:
            sinks = {str(sink['index']): sink['name'] for sink in self.pulse.listing('sinks')}
            for stream in self.pulse.listing('sink-inputs'):
                destination = sinks.get(str(stream['sink']))
                if destination:
                    data['streams'].setdefault(str(stream['index']), destination)
            self.save(data)
        try:
            self.pulse.command('set-card-profile', card['name'], target)
            current_card = self.card(card['name'])
            if current_card is None:
                raise ValueError('Audio card disappeared during the profile change')
            card_index = str(current_card['index'])
            sink = self.wait_sink(lambda value: str(value.get('card')) == card_index and '.hdmi-' in value['name'])
            data['managed_sink'] = sink['name']
            self.save(data)
            self.pulse.command('set-default-sink', sink['name'])
            if move_streams:
                for stream in self.pulse.listing('sink-inputs'):
                    self.pulse.command('move-sink-input', stream['index'], sink['name'])
        except Exception:
            try:
                self.rollback(force=True)
            except Exception as rollback_error:
                print(f'Automatic recovery needs attention: {rollback_error}; backup: {self.state}', file=sys.stderr)
            raise
        print(f"TV audio: {sink['name']}. Volume and mute were not changed. Backup: {self.state}")

    def rollback(self, force=False):
        if not self.state.exists():
            print('No managed audio preference to restore.')
            return
        data = json.loads(self.state.read_text())
        card = self.card(data['card'])
        if card is None:
            raise ValueError('Saved card is unavailable; reconnect it before rollback')
        if not force and active_profile(card) != data['managed_profile']:
            raise ValueError('Card profile changed outside this helper; inspect the backup or use --force')
        default = self.pulse.command('get-default-sink')
        if not force and data['managed_sink'] and default != data['managed_sink']:
            raise ValueError('Default output changed outside this helper; inspect the backup or use --force')
        self.pulse.command('set-card-profile', data['card'], data['previous_profile'])
        sink = self.wait_sink(lambda value: value['name'] == data['previous_default'])
        self.pulse.command('set-default-sink', sink['name'])
        existing_streams = {str(stream['index']) for stream in self.pulse.listing('sink-inputs')}
        existing_sinks = {sink['name'] for sink in self.pulse.listing('sinks')}
        for stream, destination in data['streams'].items():
            if stream in existing_streams and destination in existing_sinks:
                self.pulse.command('move-sink-input', stream, destination)
        self.state.replace(self.state.with_name('last-rollback.json'))
        print('Restored the saved card profile and default output.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'rollback'])
    parser.add_argument('--card')
    parser.add_argument('--profile')
    parser.add_argument('--move-streams', action='store_true')
    parser.add_argument('--force', action='store_true', help='explicitly replace preferences changed since installation during rollback')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as the logged-in audio session user, through the collection installer if using sudo')
    if not shutil.which('pactl'):
        parser.error('pactl is required; install CachyOS libpulse')
    fix = AudioFix()
    if args.action == 'check':
        for card in fix.pulse.listing('cards'):
            print(f"{card['name']} (active: {active_profile(card)})")
            for profile in profiles(card):
                if profile['name'].startswith('output:hdmi'):
                    print(f"  {profile['name']}: {profile.get('available', 'unknown')}")
        print('Default:', fix.pulse.command('get-default-sink'))
    elif args.action == 'install':
        fix.install(args.card, args.profile, args.move_streams)
    else:
        fix.rollback(args.force)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
