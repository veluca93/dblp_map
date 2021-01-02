# A simple script to show collaborators on a map
First run `update_dblp.sh` to download the dblp information,
then download a geoip database in `mmdb` format. The `extra_collabs.py`
file contains a list of additional collaborators for a given person.
Remember to add your Google Maps Javascript API key in `web/index.html`.

You can run this software as follows:

```
    ./dblp_map_server.py address port geoipDB [extra_collabs]
```

Note that you should not add a `.py` extension to the `extra_collabs`
parameter.
