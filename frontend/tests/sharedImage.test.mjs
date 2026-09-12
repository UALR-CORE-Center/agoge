// Run with Node 22.18+ (native TypeScript support): node --test tests/sharedImage.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {localImageNameError, suggestLocalImageName} from '../src/utilities/sharedImage.ts';
import {transformToAgogeImage, transformToAgogeImageList} from '../src/utilities/transformers/image.transform.ts';

test('copy suggestions use distinct valid names and avoid existing local copies', () => {
    const source = 'wireguard-server';
    assert.equal(suggestLocalImageName(source), 'wireguard-server-local');
    const names = ['wireguard-server-local', 'wireguard-server-local-2'];
    const suggestion = suggestLocalImageName(source, names);
    assert.equal(suggestion, 'wireguard-server-local-3');
    assert.equal(localImageNameError(suggestion, source, names), '');
});

test('legacy, image-prefixed, and maximum-length source names have usable suggestions', () => {
    for (const source of ['a'.repeat(63), 'image-wireguard', 'image-image-router', 'image', '123-router', 'My Legacy Image!', '']) {
        const suggestion = suggestLocalImageName(source);
        assert.ok(suggestion.length <= 54);
        assert.ok(`${suggestion}-manual-0`.length <= 63);
        assert.equal(localImageNameError(suggestion, source), '');
    }
});

test('copy names cannot overwrite the source or another template or use invalid resource names', () => {
    assert.match(localImageNameError('router', 'router'), /new name/);
    assert.match(localImageNameError('router-local', 'router', ['router-local']), /already exists/);
    for (const name of ['', 'UPPER', 'bad/name', '1-router', 'router-', 'a'.repeat(55), 'image-router', 'agoge', 'google']) {
        assert.ok(localImageNameError(name, 'router'));
    }
    assert.equal(localImageNameError('r', 'router'), '');
});

test('API transformation retains authoritative ownership and image compatibility metadata', () => {
    const shared = transformToAgogeImage({name: 'router', is_shared: true, source_project: 'shared-resources', architecture: 'ARM64', base_family: 'ubuntu', state_timestamp: '2026-09-12T12:00:00Z'});
    assert.equal(shared.is_shared, true);
    assert.equal(shared.source_project, 'shared-resources');
    assert.equal(shared.architecture, 'ARM64');
    assert.equal(shared.base_family, 'ubuntu');
    assert.equal(shared.state_timestamp, '2026-09-12T12:00:00Z');
    const [local] = transformToAgogeImageList([{name: 'router-local', is_shared: false, source_project: 'ualr-child', image_exists: true}]);
    assert.equal(local.is_shared, false);
    assert.equal(local.source_project, 'ualr-child');
    assert.equal(local.image_exists, true);
});
