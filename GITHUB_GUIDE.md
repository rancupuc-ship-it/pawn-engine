# Put Pawn Engine on the internet (one time, about 20 minutes)

After this, **you never touch a `.bat` file again.** GitHub builds `PawnEngine-Setup.exe` for you and
hosts your download page.

## 1. Make a GitHub account and a repository
1. Go to **github.com** and sign up (free).
2. Click the **+** at the top right, then **New repository**.
3. Name it `pawn-engine`, keep it **Public** (needed for free hosting), click **Create repository**.

## 2. Upload the project
1. Unzip `PawnEngine-1.2.zip`. Open the `pawn-engine` folder inside.
2. On your new repository page click **uploading an existing file**.
3. Select **everything inside** the `pawn-engine` folder (including the hidden `.github` folder:
   in File Explorer turn on View > Show > Hidden items) and drag it into the page.
   If dragging folders is awkward, install **GitHub Desktop** (desktop.github.com), add the folder and press *Publish*.
4. Click **Commit changes**.

## 3. Turn on the download website
1. In the repository: **Settings > Pages**.
2. Under *Build and deployment > Source* choose **GitHub Actions**.
3. Open the **Actions** tab, pick **Download website**, press **Run workflow**.
4. In a minute your site is at `https://YOURNAME.github.io/pawn-engine/`.

## 4. Publish a version (builds the installer)
1. On the repository page click **Releases > Create a new release**.
2. Click **Choose a tag**, type `v1.2`, choose *Create new tag*.
3. Click **Publish release**.
4. Open the **Actions** tab. The job **Build installer** runs for about 10–15 minutes.
5. When it is green, the release page has **PawnEngine-Setup.exe** and **PawnEngine-Portable.zip**,
   and your website's Download button works.

To publish a later version, change the code, then make a new release with `v1.3`, `v1.4`, ...
People who already have Pawn Engine see "Update available" inside the app.

## If the build fails (red X)
Open the failed step in the **Actions** tab, copy the red text and send it to me.
The most likely first-time problems are a typo in a file name or a missing Windows tool, and they are quick to fix.

## Good to know
- Windows will say **"Windows protected your PC"** on the installer because it is not code-signed. Click
  *More info > Run anyway*. A signing certificate (about $100-400 a year) removes the warning; it is optional.
- "Check for updates" only works in builds made by this GitHub workflow (it records the repository name).
- The tests run during the build; if one fails you still get an installer, but look at it.
