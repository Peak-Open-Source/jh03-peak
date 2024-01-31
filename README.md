# Protein Database Requests And Cache 

## Quickstart with single docker compose file

copy the compose file from `compose_only/compose.yaml` into your files and run 
```docker compose up```
which should automatically start the webapp.

You can now access the webapp and check the docs by going to
`0.0.0.0:8000/docs`. If this doesn't work, try `127.0.0.1:8000/docs`

## Usage

Protein files can be requested using uniprot ids. Any requested proteins
will be cached locally.

### Example Usage

* Get by uniprot ID
```
curl 'http://0.0.0.0:8000/retrieve_by_uniprot_id/p02070'
```

* Upload file and get database key as response
```
curl -w "\n" -X POST -F file=@path/to/my/file.pdb 0.0.0.0:8000/upload_pdb/
```

* see `example_scripts/` for more usage examples.

# Protein Structure Prediction

## Example Usage

* Add new protein sequence to predict structure of. Will add to calculations queue.
```
curl 'http://0.0.0.0:7000/calculate_protein_structure_from_sequence/{protein-sequence}'
```

* List all calculations (pending, processing and complete) in the calculations queue.
```
curl 'http://0.0.0.0:7000/list_calculations/'
```

* Download the .pdb protein structure file from a completed prediction (giving protein sequence to identify the result file).
```
curl 'http://0.0.0.0:7000/download_structure/{protein-sequence}'
```

### Accessing MongoDB express web service
To inspect the cache database manually, if the containers are running, go to
`0.0.0.0:8082` or `127.0.0.1:8082`.
You will need to login, the credentials are 
```
username: admin
password: pass
```

The cache database will only be present if at least one pdb file has been requested.

## Building Docker Containers Locally

### With Docker Compose

If you have `docker` and `docker compose` installed you can do
```
git clone https://github.com/eughanbell/JH03.git
cd JH03
docker compose up
```

When you edit the code, you will need to run the following first to see your changes reflected
```
docker compose build
```

### Without Docker Compose

#### Protein Structure Storage

make sure you are in this project's root folder

* build the docker image
```
docker build -t pss protein-structure-storage
```
* run the docker image
```
docker run --publish 8000:5000 pss
```

#### Protein Cache
	
build in similar way to pss, but make sure pss is still running.
```
docker build -t pc protein-cache
```
to run, we will map to 7000 instead of 8000 to not conflict with pss.
```
docker run --publish 7000:6000 pc
```

## Testing
`protein-structure-storage` unittests can be run by executing `python -m unittest` in the `protein-structure-storage/` folder.

## Running on Kubernetes

Using [minikube](https://minikube.sigs.k8s.io/docs/start/), you can simulate a kubernetes cluster locally by doing
```minikube start```

You can then add workloads and services for the cluster by using [kubectl](https://kubernetes.io/docs/tasks/tools/). Run the script at `compose_only/k8s/kubectl-apply.sh`, to start them.
You may have to wait a while for the mongo database to start.

Get the url for the protein structure storage service by using 
```minikube service pss --url```

To clear the cluster you can use the script at `compose_only/k8s/kubectl-delete.sh`.

## Pushing Built Containers to Docker Hub

This is done automaically by a gitlab pipeline.

```
docker build -t noamzeise/protein-structure-storage:latest protein-structure-storage
docker image push noamzeise/protein-structure-storage:latest
docker build -t noamzeise/protein-cache:latest protein-cache
docker image push noamzeise/protein-cache:latest
```
