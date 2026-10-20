# Collection Auto-Sort by Name Prefix

A Blender add-on that automatically files objects into collections based on
their names. Rename an object and it drops straight into the matching
collection — or spell out a whole collection path with `#` and the add-on
builds it for you.

> **Blender:** 3.0+ &nbsp;·&nbsp; **Version:** 1.3.0 &nbsp;·&nbsp; **Category:** Object

---

## Features

- **Prefix matching** — move objects into the existing collection whose name
  is the **longest** prefix of the object's name (so `enginedynamic_*` goes to
  `enginedynamic`, not `engine`).
- **Explicit `#path` creation** — names like
  `#vehicle#exterior#engine#part_object` create/reuse the nested collections
  `vehicle/exterior/engine/part` and move + rename the object into place.
- **Live Auto-Sort** — optionally re-sort an object the moment its name
  changes, powered by a safe depsgraph-watch + timer system.
- Works on **selected** objects or the **whole scene**, on-demand.
- Configurable separators (`_` and/or `.`), case sensitivity, exclusive-move,
  and match scope.

---

## Installation

1. Download `collection_autosort.py`.
2. In Blender: **Edit → Preferences → Add-ons → Install…**
3. Select the file and enable **"Collection Auto-Sort by Name Prefix"**.

Once installed, Blender keeps its own copy, so you can delete the downloaded
file (keep a backup somewhere in case of a preferences reset).

---

## Usage

### 1. Prefix matching (names without `#`)

The object is moved into the **existing** collection whose name is the longest
prefix of the object's name, followed by a separator (`_` or `.`):

| Object name               | Target collection |
| ------------------------- | ----------------- |
| `engine_metalblue`        | `engine`          |
| `enginedynamic_metalblue` | `enginedynamic`   |
| `carburettor_paintred`    | `carburettor`     |
| `nonmatching_thing`       | *(left untouched)*|

Objects whose prefix matches no existing collection are ignored.

### 2. Explicit `#path` creation (names starting with `#`)

The `#`-separated segments define a collection path. Missing collections are
created, existing ones are reused, and the object is renamed with the hashtag
prefix stripped:

```
#vehicle#exterior#engine#enginepart2_object
   └─ creates/reuses:  vehicle / exterior / engine / enginepart2
   └─ links object into 'enginepart2'
   └─ renames object to 'enginepart2_object'
```

The final collection takes the **prefix** of the leaf segment, so later
prefix-matched objects (`enginepart2_*`) also land in it.

### 3. Live Auto-Sort (react to renames)

Enable **"Live Auto-Sort (on rename)"** in the N-panel to re-sort objects
automatically the instant their name changes (using either rule above). It is
**off by default** — zero overhead until switched on.

---

## Where to run it

- **View3D → Sidebar (`N`) → "Auto-Sort" tab**, or
- **Object menu → Collection → Auto-Sort Into Collections** (opens the options
  dialog).

---

## Options

| Option              | Description                                                        |
| ------------------- | ------------------------------------------------------------------ |
| **Objects**         | Sort *Selected* only, or *All in Scene*.                           |
| **Match Against**   | *Scene Collections*, or *All Collections* in the `.blend`.         |
| **Separators**      | Treat `_` and/or `.` as prefix separators (at least one required). |
| **Case Sensitive**  | Prefix comparison case sensitivity (default off).                  |
| **Move (exclusive)**| Unlink from other collections (default), or additionally link.     |
| **Create From #Path**| Enable `#path` collection creation (default on).                  |

Live-mode defaults are configured separately in **Preferences → Add-ons →
Collection Auto-Sort** (the on-demand operator keeps its own dialog settings).

---

## How Live Auto-Sort works

Blender has no dedicated "name changed" event, so the add-on:

1. Watches `depsgraph_update_post`, comparing each object's current name to a
   cached value. Changed names are queued.
2. Performs the actual collection move from a **timer** — *outside* the
   depsgraph callback, since editing data inside it is unsafe.

Re-entry is guarded, the name cache refreshes after each sort to avoid loops,
and handlers are `@persistent` so live sorting survives opening other files.

---

## Naming convention

Object names follow `<collection>_<part/material>` (or `<collection>.<...>`),
e.g. `engine_metalblue`, `enginedynamic_pulleyA`, `carburettor_paintred`. The
prefix is what gets matched against collection names.

---

## License

This was entirely slopcoded. It's public domain.
