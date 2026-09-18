# Firebase authentication setup and troubleshooting

Configure Firebase in the **child GCP project selected in `python setup.py`**. The parent project supplies shared DNS and load-balancer routing; each child keeps its own Firebase Authentication configuration and users.

The Firebase Web API key identifies the Firebase project used by the browser. Changing `authDomain`, `projectId`, or load-balancer routing cannot change the project associated with an existing key. Use the child's key even when SendGrid, OpenAI, or Shodan secrets are shared with the parent. See [Firebase's API key documentation](https://firebase.google.com/docs/projects/api-keys).

## Values for the test-dev deployment

This example uses child project `test-dev-787001`, parent `agoge-shared-resources`, and `project_path` of `test-dev`. Substitute your selected child's values for other tenants.

| Setting or destination | Value for test-dev | Format |
| --- | --- | --- |
| Firebase/GCP project ID; generated `VITE_PROJECT_ID` | `test-dev-787001` | Child project ID |
| Setup secret `api_key`; generated `VITE_FIREBASE_KEY` | `apiKey` from the Web app registered in `test-dev-787001` | Paste only the key value |
| `firebase_auth_domain`; generated `VITE_FIREBASE_AUTH_DOMAIN` | `test-dev-787001.firebaseapp.com` | Hostname, without scheme or path |
| Firebase Authentication authorized domain | `app.agoge-labs.com` | Hostname, without scheme or tenant path |
| OAuth authorized JavaScript origins | `https://app.agoge-labs.com` and `https://test-dev-787001.firebaseapp.com` | Separate origins, without paths |
| OAuth authorized redirect URI | `https://test-dev-787001.firebaseapp.com/__/auth/handler` | Full callback URL, including the path |
| Application login/return page | `https://app.agoge-labs.com/test-dev/login` | App page; do not substitute it for the OAuth callback |
| Generated `VITE_PROJECT_PATH` | `/test-dev/` | Normalized tenant prefix |
| Generated `VITE_AGOGE_API_URL` | `https://api.agoge-labs.com/` | Shared API origin; the frontend adds the tenant prefix |

The default Firebase domain needs no tenant DNS zone or custom auth hostname. Agoge uses popup sign-in, a [Firebase-supported option for apps hosted outside Firebase Hosting](https://firebase.google.com/docs/auth/web/redirect-best-practices).

## Initial configuration in the child project

### 1. Register the Web app and obtain its key

Open [test-dev Firebase project settings](https://console.firebase.google.com/project/test-dev-787001/settings/general). Check the **Project ID** before copying anything. If the GCP project is not yet in Firebase, use **Add Firebase to an existing Google Cloud project** and select that child. See [Firebase's Web app registration instructions](https://firebase.google.com/docs/web/setup#register-app).

Under **Project settings → General → Your apps**, select the Web app. If none exists, choose **Add app → Web** and register it. Agoge already contains the Firebase SDK and deploys its UI to Cloud Run; registering the Web app does not require moving the UI to Firebase Hosting.

In **SDK setup and configuration → Config**, copy the `apiKey` value. The Firebase-generated browser key is also available under the same child's [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials?project=test-dev-787001). Use the Web configuration to identify the correct key when several keys exist. The value for setup's `api_key` is the Firebase API key, not an OAuth client ID, client secret, or service-account JSON.

Run `python setup.py`, select the child, then choose **Environment & Quotas → Synchronize Environment Variables → Specific** (enter `S`). Enter `api_key`, confirm that you want to set it, and paste only its value at the hidden input prompt. During a full installation, **All** environment setup asks for the same secret. It is saved in the selected child's Secret Manager.

### 2. Enable the sign-in providers

Open the child's [Authentication → Sign-in method](https://console.firebase.google.com/project/test-dev-787001/authentication/providers). Initialize Authentication if prompted. Enable **Google**, select the project support email, and save. Enable **Email/Password** if you use Agoge's email sign-in option. Provider configuration is described in [Firebase's Google sign-in guide](https://firebase.google.com/docs/auth/web/google-signin).

### 3. Authorize the shared app hostname

Open [Authentication → Settings → Authorized domains](https://console.firebase.google.com/project/test-dev-787001/authentication/settings). Add `app.agoge-labs.com` and retain the child's default Firebase domains. For local development, add the hostnames you actually use, such as `localhost`.

Enter only hostnames in this list. The tenant path `/test-dev` is handled by Agoge and the shared load balancer; it is not part of a Firebase authorized-domain entry. Adding the shared hostname to another child's list does not configure this child.

### 4. Check the Google OAuth client used by Firebase

In the Google provider's configuration, identify its **Web client ID**. Open that existing Web client in the child's [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients?project=test-dev-787001). It may also be listed under **APIs & Services → Credentials → OAuth 2.0 Client IDs**. Match the client ID instead of creating a separate, unused client.

Use the origins and callback from the table above, retaining any existing entries needed by this child. The callback must match the configured Firebase auth domain and end in `/__/auth/handler`. Google documents the required formats and matching rules in [Manage OAuth Clients](https://support.google.com/cloud/answer/15549257).

If the OAuth consent configuration is in Testing mode, ensure the intended tester is allowed under **Google Auth Platform → Audience → Test users**. See [Google's OAuth audience configuration](https://developers.google.com/workspace/guides/configure-oauth-consent).

### 5. Build and verify React

Continue the full installation, or use **Application Installation and Updates → Update Main Application Only → Specific → React** for an existing app. In that deployment submenu, **Specific** is `1` and **React** is `1`. Check the effective child project, Firebase domain, app hostname, and callback printed by setup.

If setup finds an older custom `firebase_auth_domain`, press **Enter** to save and use `<child-project>.firebaseapp.com`. Choose **K** only for a working custom domain configured in this same child, or **C** to cancel deployment.

After deployment, reload the login page and try Google sign-in. Confirm the callback uses the child's Firebase domain and the app returns to the correct tenant path. Check **Authentication → Users** in the child when verifying the resulting Firebase account. Application access after Firebase sign-in also requires the user's Agoge account and permissions.

## What setup does automatically

| Setup handles | Complete in the consoles |
| --- | --- |
| Saves the selected child's `api_key` when entered in environment setup | Add Firebase to the child and obtain the Web app's key |
| Checks the key against the target's actual Resource Manager project identity before React builds | Enable Google and other required providers |
| Selects and saves the default or retained custom auth domain | Authorize the shared app hostname and configure any custom auth domain |
| Generates the production frontend environment and builds the React image | Check the Google provider's OAuth client, callback, and access for testers |
| Configures shared load-balancer routing after app readiness checks | Maintain the shared DNS and certificates |

The pre-build check stops on a missing or mismatched key, unavailable project metadata, or a failed Firebase configuration request. The setup account needs `resourcemanager.projects.get` on the child. This check verifies the key's project; it does not verify provider settings or complete a sign-in. See [deployment behavior and permissions](shared-project-setup.md#firebase-configuration-during-deployment).

## Repair an existing deployment

1. Pull the current setup branch and restart `python setup.py`. Select the child by its project ID.
2. Obtain that child's Web app `apiKey` as described above. Set **Environment & Quotas → Synchronize Environment Variables → Specific → api_key**.
3. Complete the provider, authorized-domain, and OAuth-client checklist in that same child's consoles.
4. Choose **Application Installation and Updates → Update Main Application Only → Specific → React**. Accept the default child Firebase domain if replacing an obsolete override.
5. After the deployment finishes, reload the app with the browser cache disabled and test sign-in again.

**React must be rebuilt after changing its Firebase key or auth domain.** Vite replaces frontend environment values during compilation, so Cloud Run runtime environment edits do not change an existing JavaScript bundle. The same applies to the frontend project ID, tenant path, and API origin. See [Vite environment variables](https://vite.dev/guide/env-and-mode).

Console-only provider, authorized-domain, or OAuth-client edits do not by themselves require a React rebuild when the embedded values stay the same. Setup restores pre-existing local environment files after a build, so an older local `frontend/.env.production` afterward is not evidence of what was uploaded. Use setup's build summary and the deployed app to check effective values.

## Troubleshooting

| Symptom | What to check and do |
| --- | --- |
| Firebase configuration reports another child's project or domains, such as `agoge-ualr` on `test-dev` | Compare the returned `projectId` with the child's project ID/number in Firebase Project settings; the public configuration response can use the numeric project number. If it differs, replace the child's saved `api_key` and rebuild React. If it matches, check the authorized-domain list in that child. This response does not establish which Cloud Run service served the page. |
| Setup reports that `api_key` selects a different project | Follow the same key replacement procedure. Changing `firebase_auth_domain` or a saved `project_number` will not repair the key. |
| Popup still opens an old auth hostname, or deployed Firebase values remain old | Confirm the latest build included React for the intended child. Check the selected domain and reload the deployed page without the browser cache. Runtime-only or API-only updates cannot replace the bundle. |
| `auth/unauthorized-domain` | Add the actual app hostname to the intended child's Firebase authorized domains, then retry. First verify that the browser's key selects that child. |
| `auth/invalid-continue-uri` | Inspect the failed Firebase request in browser Network tools and its `continueUri` or `requestUri` value. Check for a malformed or missing URL and confirm the tenant's project/key/domain agree. Share only the relevant URL fields and error text when seeking help. |
| `auth/unauthorized-continue-uri` | Check that the continue URL's hostname is authorized in the Firebase project selected by the key. This is a domain-authorization error; `invalid-continue-uri` instead concerns a valid URL string. See [Firebase's error reference](https://firebase.google.com/docs/auth/admin/errors). |
| Google reports `redirect_uri_mismatch` or `origin_mismatch` | Check the actual request's `client_id`, callback, and origin against the Web client used by this child's Google provider. Use the callback and origin formats in the table above. |
| Firebase pre-build check fails with HTTP 403 | Check the child key's API and HTTP-referrer restrictions in Credentials. They must allow Firebase Authentication and requests from the printed app origin. Follow [Firebase's key restriction guidance](https://firebase.google.com/docs/projects/api-keys), retaining restrictions required for the app. |
| Setup cannot read project metadata | Refresh setup credentials with `python setup.py --reauthenticate` and confirm that identity can read the selected child's project metadata. |

## Existing custom authentication domains

Use `<child-project>.firebaseapp.com` for a new shared deployment. To retain a custom `firebase_auth_domain`, connect it to Firebase Hosting in that child, complete its DNS/certificate setup, authorize it in Firebase, and configure `https://<custom-domain>/__/auth/handler` on that child's Google OAuth client. Then retain it with **K** during the React build. Follow [Firebase's custom redirect-domain instructions](https://firebase.google.com/docs/auth/web/google-signin#customizing-the-redirect-domain-for-google-sign-in).

A shared application hostname or a load-balancer path alone does not configure a Firebase authentication handler. Keep the custom domain, Firebase key, and OAuth provider configuration aligned with the same child project.
