# Code YOE patch response validation

The single-file patch workflow now rejects non-object JSON before accessing `noChange`. Invalid shapes enter the existing safe warning path: the draft/review remain available, status is COMPLETED, and no file is changed. Valid patches retain explicit approval.

The real Engine.run path reproduced six AttributeErrors before the fix (arrays, null, string, number, boolean). After the fix, all 55 portable tests pass, including four regression tests with multiple invalid-shape cases, malformed JSON, no-change and valid approval-required patches. No inference, shell execution or production-file changes occur in these tests.

This fix is newer than the packaged native preview installers in tag v2.0.20261107-native-preview. Those installer assets and matching archives remain unchanged. It is a source fix and is not claimed deployed in those EXEs.
