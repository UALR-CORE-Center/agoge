// Run with Node 22.18+ (native TypeScript support): node --test tests/imageArchitecture.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {
    getImageArchitecture, imageArchitectureLabel, serverImageArchitectureError,
} from '../src/utilities/imageArchitecture.ts';

test('the reported Ubuntu Minimal ARM64 image is blocked even in a legacy catalog', () => {
    const image = {
        self_link: 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-minimal-2204-jammy-arm64-v20260906',
    };
    assert.equal(getImageArchitecture(image), 'ARM64');
    assert.match(serverImageArchitectureError(image), /ARM64.*E2.*AMD64/);
    assert.equal(imageArchitectureLabel(image), 'ARM64');
});

test('live architecture metadata takes precedence over descriptive names', () => {
    const image = {architecture: 'ARM64', name: 'Ubuntu amd64'};
    assert.equal(getImageArchitecture(image), 'ARM64');
    assert.ok(serverImageArchitectureError(image));
});

test('AMD64 aliases are displayed consistently and remain selectable', () => {
    for (const architecture of ['X86_64', 'AMD64', 'x86-64']) {
        const image = {architecture};
        assert.equal(getImageArchitecture(image), 'X86_64');
        assert.equal(imageArchitectureLabel(image), 'AMD64 (x86-64)');
        assert.equal(serverImageArchitectureError(image), '');
    }
    assert.equal(getImageArchitecture({family: 'ubuntu-2404-lts-amd64'}), 'X86_64');
});

test('unknown custom image architecture is not guessed from its machine or name', () => {
    const image = {name: 'my-custom-router', architecture: null, machine_type: 'e2-medium'};
    assert.equal(getImageArchitecture(image), undefined);
    assert.equal(imageArchitectureLabel(image), 'Unknown');
    assert.equal(serverImageArchitectureError(image), '');
    assert.equal(getImageArchitecture({name: 'myarm64router'}), undefined);
    assert.equal(getImageArchitecture({name: 'legacy-router', base_family: [null]}), undefined);
});

test('legacy source URLs take precedence over stale family descriptions', () => {
    assert.equal(getImageArchitecture({self_link: 'projects/shared/global/images/router-arm64-v1', family: 'ubuntu-amd64'}), 'ARM64');
    assert.equal(getImageArchitecture({base_family: 'ubuntu-minimal-2204-lts-arm64'}), 'ARM64');
});
