FROM amazonlinux:1
RUN yum install -y python3-devel python36-pip zip postgresql-devel && yum clean all
COPY src /build
RUN pip-3.6 install -r /build/requirements.txt -t /build/python/
WORKDIR /build
CMD sh build_package.sh
