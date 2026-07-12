suyeon96
Suyeon's Blog
호기심 많은 개발자의 기록
   
검색
분류 전체보기 (52)
IT (41)
 Programming (2)
 Computer Science (6)
 Data Structure (11)
 Design Pattern (0)
 Cloud (11)
 AI (0)
 Etc (11)
Media (8)
 Media Science (8)
 Multimedia Contents (0)
 기타 (0)
Life (3)
 Travel (0)
 Tech (1)
 Economy (2)
최근 글
[가상화] Xen과 KVM 하이퍼바이저 아키텍처
2022.02.09
[가상화] Xen과 KVM 하이퍼바이저 아키텍처
[가상화] Full Virtualization & Para⋯
2022.02.08
[가상화] Full Virtualization & Para⋯
[가상화] 하이퍼바이저와 가상화
2022.02.07
[가상화] 하이퍼바이저와 가상화
[Network] ONOS로 Open vSwitch 제어하⋯
2022.02.01
[Network] ONOS로 Open vSwitch 제어하⋯
[Network] Virtual Network와 Open ⋯
2022.01.30
[Network] Virtual Network와 Open ⋯
최근 댓글
감사합니다.
김진호
감사합니다.
지수부 3의 2진코드는 101이 아닌 011아닌가요?
oh
안녕하세요 잘 봤습니다. 그런데 궁금한점이 왜 삽입이나 삭⋯
수퍼초보
큰 도움이 됐습니다 감사합니다!
devria
태그
EC2
kibana
logstash
Virtualization
elk stack
elasticsearch
hypervisor
AWS
OVS
Open vSwitch
전체 방문자
378,686
오늘
28
어제
36
suyeon96

IT/Cloud
[Network] SDN(Software Defined Network) 이란?
2021. 7. 26. 10:27


SDN이란?
SDN(Software Defined Network)이란 소프트웨어를 통해 네트워크 리소스를 가상화하고 추상화하는 네트워크 인프라에 대한 접근 방식을 의미한다.

조금 더 쉽게 설명하자면, 소프트웨어 애플리케이션과 API를 이용하여 네트워크를 프로그래밍하고, 중앙에서 전체 네트워크를 제어하고 관리하는 것이다.

 

SDN 작동방식
SDN에서 가장 핵심은 네트워크 장비의 Control Plane(제어부)와 Data Plane(전송부)의 분리이다.

Control Plane은 네트워크 장비를 제어하는 뇌에 해당하고, Data Plane은 데이터를 전송하는 역할을 하는 것이다.


 

기존의 라우터(Router)라는 네트워크 장비에는 제어부와 전송부가 같이 존재한다.

제어부에서 최적의 경로를 계산하고 전송부가 데이터를 전송하는 방식이다.

 

따라서 네트워크 운영자는 각각의 네트워크 장비를 수동으로 관리해야 했으며, 전체 기능이 필요하지 않은 경우에도 비싼 라우터를 구매하여 사용하는 수밖에 없었다.

(* 첨언으로 Cisco는 전 세계의 네트워크 장비를 수십 년간 거의 독점적으로 공급하며 어마어마하게 성장하였다.)

 

SDN을 적용하면 제어부와 전송부를 분리한다.

제어부를 별도의 컴퓨팅 서버로 분리하고, 네트워크 장비는 데이터 전송 기능만 담당하도록 하는 것이다.

 

SDN 장점
1. 비용 절감

제어부는 여러 네트워크 장비를 제어할 수 있기 때문에 관리가 관소화 되고 운영에 들어가는 비용을 줄일 수 있다.

또한, 각 장비의 사양을 각각의 기능에 최적화시킬 수 있으므로 더 이상 눈물을 머금고 리소스의 낭비를 보고 있을 필요가 없다.

 

2. 확장성 및 유연성

"가상화"라는 기술을 설명할 때 항상 따라오는 장점이다.

SDN 또한 네트워크를 가상화한다는 점에서 마찬가지이다.

하드웨어를 소프트웨어로 전환하며, 더 이상 물리적인 리소스의 한계에 구애받지 않아도 된다.

원하는 시기에 필요한 만큼 네트워크 리소스를 확장하거나 축소할 수 있다.

벤더 별로 각각의 장치를 프로그래밍하고 그 한계에 타협하는 상황에서 벗어나, 네트워크 장비를 선택할 때 더 높은 유연성을 확보할 수 있게 된다.

 

 

SDN의 역사
아래 지표에서 볼 수 있듯이 네트워크를 프로그래밍 하는 것은 과거 20년 전부터 지속해서 발전해왔다.


 

컴퓨터와 통신에 있어 네트워크는 정말 중요한 분야이다. (매우 기본이지만 매우 어렵기도 하다..)

Legacy 네트워크와 별개로 우리는 네트워크를 Software화 시키는 것이 왜 중요한지, 이를 위해 역사상 어떤 노력들이 진행되어 왔는지 살펴볼 필요가 있다.

위 지표를 가져온 논문(The Road to SDN: An Intellectual History of Programmable Networks)에서 이를 확인할 수 있다.

 

하나하나 짚고 넘어가고 싶지만, 글이 너무 길어질 것 같아 (사실 필자가 글로 서술할 정도로 완벽하게 이해하지 못함) 넘어간다..

하지만 SDN의 창시자로 불리는 Scott Shenker(UC버클리 교수)과 Nick Mckeown(스탠포드 대학 교수) 2명은 알아두도록 하자.

이들을 비롯한 SDN 창시자들은 ONF(Open Networking Foundation)라는 비영리 단체를 만들고, OpenFlow와 SDN Controller ONOS(Open Network Operating System)를 개발하였다.

 

구글 G-scale 발표
실제로 SDN이 현업에 적용되며 빠르게 발전한 계기는 2012년 4월 구글에서 G-scale SDN 적용 사례를 발표하고 나서부터가 아닌가 싶다.

G-Scale은 구글이 2010년에 시작한 OpenFlow 프로젝트로 전 세계에 흩어져있는 구글 데이터센터 백본(Backbone) 구간을 SDN 기반으로 전환하는 프로젝트이다.


 

백본(Backbone) 네트워크는 사용자 네트워크와 다르게 한번에 대용량 데이터가 전송된다.

(참고 : 백본 네트워크 - 데이터센터 간 연결망, 사용자 네트워크 - 사용자와 구글 서비스의 연결망)

딱 봐도 어마어마하게 많은 구글의 초울트라 빅데이터들을 옮기는 작업은 보통 어려운 일이 아닐 것이다.

이에 구글은 자체적으로 네트워크 장비를 제작하고 Openflow를 도입하여 SDN을 구현하고 이를 해결하였다.

 

SDN 적용으로 구글은 크게 3가지 이득을 볼 수 있었다.

1. 50% → 100%

기존의 Legacy Network 인프라의 경우 리소스 활용률이 평균 50%가 채 되지 못한다고 한다.

각각의 네트워크 장비들이 벤더에 종속되어 있어 호환성 문제로 기능을 100% 활용할 수 없을 뿐만 아니라 전체 네트워크 스위치들에 대한 컨트롤이 불가능하기 때문이다.

위에서 언급했듯이 다양한 네트워크 상황에 딱맞는 장비를 구할 수도 없기 때문에 오버스펙의 장비를 구매해야 한다.

하지만 구글은 SDN을 구현하여 거의 100%에 가까운 인프라 리소스 활용률을 만들어냈다. ㄷㄷ

 

2. WAN(Wide Area Network) 분야에서의 경로 최적화

WAN대역에서 가장 빠른 경로를 계산하여 데이터 전송 속도를 높이고, 사용자에게는 빠르고 고품질의 서비스를 제공하게 되었다.

구글은 전 세계를 대상으로 하는 서비스이기 때문에 WAN 대역에서의 데이터 전송 성능 향상은 더욱 중요하였다.

 

3. 비용 절감

SDN 컨트롤러와 화이트박스 스위치의 조합을 통해 데이터센터 내의 네트워크 구축 비용을 획기적으로 낮췄다.

화이트박스 스위치(WhiteBox Switch)란 SDN에서 나온 개념으로 기존 레거시 장비의 제어 방식이 공개가 안 돼서 ‘블랙박스’라고 불리는 것과 반대의 개념이다. 네트워크 장비의 동작 방식을 사용자가 결정하고 투명하게 공개되어 있다는 의미이다.

또한 동시에 데이터센터 내의 서비스 트래픽 특성을 전체적으로 파악하여 최적의 네트워크를 구성하고, 비용 또한 최적화시킬 수 있었다.

 

이후 세계의 통신사들은 주도적으로 SDN을 도입하고 네트워크를 가상화하기 시작하였으며, 네트워크 장비 제조사들 또한 SDN의 주도권을 가지기 위해 적극적으로 뛰어들게 된다.

참고로 오래되고 대표적인 SDN업체 Nicira가 2012년 VMware에 인수되었다. Cisco는 2014년 Tail-f와 Insieme을 인수하고, 오픈 커뮤니티를 이끌며 오픈 데이라이트(Open Daylight)라는 SDN Controller를 개발하였다.

 

 

SDN Architecture
SDN 아키텍처는 Application Layer, Control Plane(SDN 컨트롤러), Data Plane(SDN 전송 장비) 으로 구성되는 3 계층 구조로 표현할 수 있다.

그리고 계층 간 연동을 위해서 Southbound Interface(ex. OpenFlow)와 Northbound Interface가 존재한다.


출처 : Unveil the Myths About SDN Switch FS Community
 

Application Layer
Routing, Loadbalance, ACL 등 네트워크를 제어하는 데 사용되는 소프트웨어 애플리케이션들이다.

SDN 컨트롤러에서 제공받은 API와 여러 서비스들을 이용하여 Control 기능을 구현한다.

 

SDN Controller
SDN 컨트롤러는 전체 네트워크 자원에 대한 중앙 집중적 제어를 담당하는 네트워크 운영체제 역할을 담당한다.

중앙 집중적 네트워크 제어를 위해 글로벌 뷰를 기반으로 포워딩을 제어하고 토폴로지 및 자원의 상태를 관리하는 기본 기능을 수행한다.

또한 여러 네트워크 장비와 통신할 수 있도록 South-bound API를 제공하거나 추가할 수 있으며, 여러 가지 기능의 애플리케이션을 개발하고 다른 운영 도구과 통신할 수 있게 해주는 North-bound API도 제공한다.

 

대표적인 SDN Controller에는 위에서 언급했듯이 ONF의 주도로 만들어진 ONOS가 있으며, 이 외에도 Floodlight, Trema, Maestro, Opendaylight 등이 있다.

 

Data Plane
Data Plane의 SDN 디바이스는 SDN 컨트롤러의 지시에 따라 패킷 전송을 수행하는 네트워크 장치를 통칭한다.

앞서 구글의 사례에서 보았듯이 SDN의 개념과 화이트박스 스위치와를 이용하여 레거시 장비 대비 획기적으로 낮은 가격으로 데이터센터의 네트워크를 구축할 수 있다.

 

OpenFlow
기존 레거시 장비에서는 Control Planer과 Data Plane이 하나의 장비 내에 같이 탑재되었기 때문에 통신이 필요 없었다.

하지만 SDN에서는 Control Planer과 Data Plane이 구분되며, SDN 컨트롤러는 Data Plane 계층에 대한 포워딩을 제어(Match & Action)하고 정보를 수집하기 위해 Southbound 인터페이스를 사용한다.

이 표준 통신(RPC) 규격 중 하나가 바로 ONF에서 정의하고있는 OpenFlow Protocol이다.


 

즉, OpenFlow는 이론으로만 가능했던 SDN을 구현하기 위해 처음으로 제정된 최초의 표준 통신 인터페이스이다.

 

OpenFlow는 OpenFlow 스위치, OpenFlow 컨트롤러로 구성되며, 흐름(flow) 정보를 제어하여 패킷의 전달 경로 및 방식을 결정한다.

OpenFlow 스위치 내부에는 패킷 전달 경로와 방식에 대한 정보를 가지고 있는 FlowTable이라는 것이 존재한다.

패킷이 발생하면 제일 먼저 FlowTable이 해당 패킷에 대한 정보를 가지고 있는지 확인하고, 없다면 패킷에 대한 제어 정보를 OpenFlow 컨트롤러에 요청하는 것이다.

OpenFlow 컨트롤러 내의 패킷 제어 정보는 외부에서 API를 통해 입력할 수 있다.

 

 

Reference
https://opennetworking.org/sdn-definition/
https://www.cs.princeton.edu/courses/archive/fall13/cos597E/papers/sdnhistory.pdf
https://www.koreascience.or.kr/article/JAKO201302757805044.pdf
https://www.sktinsight.com/98995
https://d2.naver.com/helloworld/387756
 

 

 



11

'IT/Cloud' 카테고리의 다른 글
[Network] Virtual Network와 Open vSwitch (네트워크 가상화)
[Network] SDN/NFV의 관계와 차이 (feat. VNF, CNF)
[AWS] AWS CloudFormation으로 인프라 배포 자동화
[AWS] 단계별 시나리오를 통해 알아보는 EC2 Auto Scaling
cloudG-ScalenetworkOpenflowSDN
댓글
URL 복사
카카오톡 공유
페이스북 공유
엑스 공유
신고하기
suyeon96
suyeon96
호기심 많은 개발자의 기록
Suyeon's Blog
호기심 많은 개발자의 기록

구독하기
댓글
이름
암호
댓글쓰기
지나가는 행인
2022.10.24 17:42 신고
진짜 정리 잘하셨네요 공부방법 배우고 싶어요 ㅋㅋㅋ
수정/삭제댓글쓰기댓글보기
Kick_snare
2022.12.12 22:58 신고
정리 잘하셨네요 잘읽고갑니다!
수정/삭제댓글쓰기댓글보기
익명
2023.09.21 23:45
비밀댓글입니다.
수정/삭제댓글쓰기댓글보기
테마 바꾸기
제일 위로



클라우드 네트워크 관리 기술, OpenFlow
2013.06.01|62572
클라우드 환경에서는 간단한 사용자 조작으로 네트워크 부하를 분산하고 트래픽을 모니터링하며 서로 다른 데이터 센터나 서로 다른 지역 또는 서로 다른 국가에서 운영 중인 서버에 대해 네트워크를 관리할 수 있도록 하는 기술이 필요합니다. 이번 글에서는 클라우드 네트워크를 효율적으로 관리할 수 있는 기술 중 하나인 OpenFlow에 대해서 이야기하겠습니다.

클라우드 환경의 네트워크 관리
클라우드 서비스에는 다음 그림과 같이, 하나의 물리 서버에서 하나 이상의 가상 머신(virtual machine, 이하 VM)을 제공하는 서버 가상화 기술뿐만 아니라, 물리 네트워크에서 가상의 네트워크 환경을 제공하는 네트워크 가상화 기술도 적용되어 있다.

openflow1

그림 1 클라우드 네트워크 구성

이와 같은 클라우드 환경에서는 몇 가지 사항이 만족돼야 한다.

첫 번째는 보안(security)이다. 공통의 물리 네트워크 인프라를 여러 명의 사용자가 공유해서 사용해야 하기 때문에, 가상 네트워크 인프라에서는 서로 다른 사용자의 VM 간에 보안이 보장되어야 한다.

두 번째는 자동화(automation)이다. 일반적인 서비스 환경에서는 네트워크 설정 정보를 추가하거나 변경하려면 네트워크 관리자에게 요청해야 하며, 완료되기까지 시간이 소요된다. 하지만 클라우드 환경에서는 사용자가 간단히 조작하여 네트워크를 설정하고 설정이 즉시 반영될 수 있어야 한다. 이를 위해서는 요청이 즉시 반영될 수 있도록 자동화해야 한다.

세 번째는 확장성(scalability)이다. 클라우드 서비스의 장점 중 하나는 필요한 VM을 빠른 시간 내에 투입할 수 있다는 것이다. 이렇게 투입된 VM의 지역이나 국가가 다르거나, 전체 VM 수가 수백 대 또는 수천 대여도 쉽게 네트워크 환경을 구축할 수 있어야 한다.

보안, 자동화, 확장성을 보장하려면 네트워크 기술이 다음의 조건을 만족해야 한다.

자유롭게 네트워크를 만들고 다양한 서비스를 제공할 수 있도록 유연성이 있어야 한다.
네트워크를 동적으로 관리할 수 있도록 기능이 모듈화되어 있어야 한다.
위 두 가지를 만족하기 위해서는 네트워크 요소들을 프로그래밍할 수 있어야 한다.
위 조건을 모두 만족시키는 아키텍처 중 하나로 SDN(Software Defined Network)이 있다.

SDN
학교나 연구소는 새로운 네트워크 프로토콜을 개발하고 테스트하고 싶어 한다. 그런데 테스트하기 위해 별도의 네트워크 환경을 구축하려면 비용이 많이 들고, 운영 중인 네트워크 환경에서 새로운 프로토콜을 테스트하면 장애를 유발하는 등 운영에 영향을 미칠 가능성이 있다. 이로 인해 하나의 물리 네트워크 환경에서 다수의 가상 네트워크 환경을 구축할 수 있는 방법을 연구하기 시작했고, 그 결과 SDN이라는 개념이 등장했다.

다음 그림에서 보는 것처럼, 네트워크 장비가 포함된 인프라 계층은 단순히 패킷을 전달하는 역할만 하고, SDN 제어 소프트웨어를 프로그래밍하여 패킷의 흐름을 제어하므로 하나의 네트워크 인프라에서 다양한 네트워크 환경을 구축할 수 있다. 즉, SDN에서는 패킷이 발생했을 때 네트워크 장비는 패킷을 어디로 전달할지 SDN 제어 소프트웨어에게 물어보고, 그 결과를 반영하여 패킷을 전송하는 경로와 방식을 결정한다.

openflow2

그림 2 SDN 아키텍처(이미지 출처)

하지만 SDN은 이론적인 개념으로, 실제로 적용하려면 이를 구현할 방안이 필요했다. 이 SDN을 구현하기 위해 Stanford University에서 제안한 내용이 OpenFlow이다.

OpenFlow 소개
OpenFlow는 SDN을 구현하기 위해 처음으로 제정된 표준 인터페이스이다. 다음 그림과 같이 OpenFlow 스위치, OpenFlow 컨트롤러로 구성되며, 흐름(flow) 정보를 제어하여 패킷의 전달 경로 및 방식을 결정한다.

흐름 흐름(flow)은 "특정 시간 동안 네트워크상의 지정된 관찰 지점을 지나가는 패킷의 집합"이라고 정의된다. 간단히 이야기하면 흐름이란 패킷의 출발지와 목적지 정보 등을 가진 데이터라고 할 수 있다("네트워크 트래픽 분석 기술, NetFlow 소개와 활용" 참조).

openflow3

그림 3 OpenFlow 시스템 구성(이미지 출처)

OpenFlow 동작 방식
OpenFlow 스위치 내부에는 패킷 전달 경로와 방식에 대한 정보를 가지고 있는 FlowTable이라는 것이 존재한다. 패킷이 발생하면 제일 먼저 FlowTable이 해당 패킷에 대한 정보를 가지고 있는지 확인한다. 패킷에 대한 정보가 존재하면 그에 맞춰 패킷을 처리하고, 정보가 존재하지 않으면 해당 패킷에 대한 제어 정보를 OpenFlow 컨트롤러에 요청한다.

스위치로부터 제어 정보를 요청받은 OpenFlow 컨트롤러는 내부에 존재하는 패킷 제어 정보를 확인하고, 해당 결과를 OpenFlow 스위치에 전달한다. OpenFlow 컨트롤러 내의 패킷 제어 정보는 외부의 프로그램에서 API를 통해 입력할 수 있다.

OpenFlow 스위치는 컨트롤러로부터 전달 받은 제어 정보를 FlowTable에 저장하고, 이후 동일한 패킷이 발생하면 FlowTable에 있는 정보를 활용하여 패킷을 전달한다.

OpenFlow 패킷 제어 정보
앞에서 언급했듯이 OpenFlow에서 패킷을 제어하는 정보는 FlowTable에 저장되어 있으며, 다음 그림과 같이 Header Fields, Counters, Actions로 구성된다.

openflow4

그림 4 Flow Entry 구성 요소

헤더 필드(header fields)에는 스위치 포트, 이더넷 및 프로토콜 정보, 출발지(source)/목적지(destination)의 MAC·IP·포트·우선순위가 저장된다. 헤더 필드 정보와 패킷의 정보의 일치 여부에 따라, 발생한 패킷이 FlowTable에 존재하는지 결정한다.

액션(actions)은 패킷 정보가 헤더 필드 정보와 일치할 때 어떻게 패킷을 처리할지에 대한 정보를 담고 있으며, 처리 방식은 다음 3가지가 있다.

스위치에 정의되어 있는 경로에 따라 패킷 전달
정해진 하나의 포트 또는 여러 개의 포트로 패킷 전달(전달 경로 변경)
패킷이 더 이상 전달되지 못하도록 차단(drop)
카운터(counters)는 FlowTable에 제어 정보가 등록된 순간부터 현재까지의 시간을 측정하는 용도로 사용된다. FlowTable에 등록된 제어 정보는 영구적으로 저장하거나 정해진 시간 동안만 유지할 수 있는데, 카운터는 후자의 경우 생명 주기(life cycle) 관리에 사용된다.

OpenFlow 적용 예
앞에서 클라우드 환경의 네트워크는 보안, 자동화, 확장성을 보장해야 한다고 했는데, OpenFlow에서 이를 어떻게 보장하는지 살펴보자.

다음과 같은 2명의 사용자가 생성한 VM 그룹이 있다고 가정해 보자.

openflow5

그림 5 OpenFlow 적용 예

보안을 위해서는 각 사용자가 생성한 VM끼리만 통신할 수 있어야 하는데, OpenFlow의 FlowTable을 다음과 같이 구성하면 이를 해결할 수 있다.

표 1 FlowTable 설정 예

SrcIp	DestIp	Protocol	SrcPort	DestPort	Priority	…	Action
10.0.0.2	10.0.0.3	*	*	*	0	*	NORMAL
10.0.0.3	10.0.0.2	*	*	*	0	*	NORMAL
10.0.0.4	10.0.0.5	*	*	*	0	*	NORMAL
10.0.0.5	10.0.0.4	*	*	*	0	*	NORMAL
*	*	*	*	*	65535	*	DROP
10.0.0.2, 10.0.0.3 간의 패킷과 10.0.0.4, 10.0.0.5 간의 패킷만 전달하고 다른 모든 패킷은 drop하도록 설정되어 있다.

네트워크 설정을 자동화하려면 VM이 생성될 때마다 자동으로 위와 같이 설정되어야 한다. 외부 프로그램에서 API로 OpenFlow 컨트롤러에 정보를 입력할 수 있으므로, 해당 VM이 생성될 때 관리 프로그램에서 API를 호출해 관련 정보를 설정하도록 하면 이 또한 쉽게 해결할 수 있다.

그리고 확장성을 보장하려면 네트워크 환경을 쉽게 구축할 수 있어야 한다. OpenFlow 스위치를 추가할 때에는 기존의 OpenFlow 컨트롤러와 연결하기만 하면 되고, OpenFlow 컨트롤러를 추가할 때에는 API로 패킷 제어 정보를 일괄 등록하고 OpenFlow 스위치와 연결하기만 하면 된다. 따라서 쉽고 빠르게 네트워크 환경을 구축할 수 있다.

마치며
OpenFlow는 그 개념이 정립되고 적용되기 시작한 지 몇 년밖에 안 된, 성숙되지는 않은 기술이다. 이 번 글을 통해 향후 시장이 성숙되면 클라우드 환경에서 꼭 필요한 기술이 될 것이라고 생각되는 OpenFlow에 대해 이해하는데 도움이 되었기를 바란다.

참고 자료
https://www.opennetworking.org/sdn-resources/sdn-defined
http://www.openflow.org/documents/openflow-wp-latest.pdf
https://www.opennetworking.org/images/stories/downloads/sdn-resources/onf-specifications/openflow/openflow-spec-v1.0.0.pdf
Tag
네트워크openflowsdnvm가상화
	
박민수|NBP 클라우드플랫폼개발랩Hadoop을 이용한 분석 시스템 개발로 입문해서 지금은 클라우드 서비스를 개발하고 있다. 배워야 할게 너무 많지만 새로운 것을 알아가며 하루 하루를 즐겁게 보내려고 노력하는 개발자이다.

NAVER

facebook

URL
관련글

썸네일
클라우드 환경에서 ARP 스푸핑 방지 메커니즘 구현하기
썸네일
구르믈 버서난 달처럼
썸네일
OpenStack Summit 2016 참관기
썸네일
JVM Internal
댓글3

댓글 입력
주제와 무관한 댓글, 악플은 삭제될 수 있습니다.
최동화
전체적인 SDN 개념과 OpenFlow에 대한 이해가 됐습니다. 감사합니다.
2020-07-30 21:49
답글0공감/비공감
공감
0
비공감
0
김글로리
이 글을보고 SDN과 OPENFLOW의 개념에 대해 어느정도 이해가 됐습니다. 감사합니다!
2020-04-11 22:24
답글0공감/비공감
공감
0
비공감
0
페이스북
추숙
옵션 열기
좋은 자료 공유 감사합니다^^
2013-06-03 08:30
답글0공감/비공감
공감
0
비공감
0
NAVER Developers
DAN
OpenSource
D2 STARTUP FACTORY
Copyright © NAVER Corp. All Rights Reserved.



