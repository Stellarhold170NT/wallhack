2
2
0
2
c
e
D
6
2

]

V
C
.
s
c
[

1
v
1
6
1
3
1
.
2
1
2
2
:
v
i
X
r
a

HUMAN ACTIVITY RECOGNITION FROM WI-FI CSI DATA
USING PRINCIPAL COMPONENT-BASED WAVELET CNN

PREPRINT SUBMITTED TO ELSEVIER

Ishtiaque Ahmed Showmik
1606035@eee.buet.ac.bd

Tahsina Farah Sanam
tahsina@iat.buet.ac.bd

Haﬁz Imtiaz
haﬁzimtiaz@eee.buet.ac.bd

December 27, 2022

ABSTRACT

Human Activity Recognition (HAR) is an emerging technology with several applications in surveil-
lance, security, and healthcare sectors. Noninvasive HAR systems based on Wi-Fi Channel State
Information (CSI) signals can be developed leveraging the quick growth of ubiquitous Wi-Fi technolo-
gies, and the correlation between CSI dynamics and body motions. In this paper, we propose Principal
Component-based Wavelet Convolutional Neural Network (or PCWCNN) – a novel approach that of-
fers robustness and efﬁciency for practical real-time applications. Our proposed method incorporates
two efﬁcient preprocessing algorithms – the Principal Component Analysis (PCA) and the Discrete
Wavelet Transform (DWT). We employ an adaptive activity segmentation algorithm that is accurate
and computationally light. Additionally, we used the Wavelet CNN for classiﬁcation, which is a deep
convolutional network analogous to the well-studied ResNet and DenseNet networks. We empirically
show that our proposed PCWCNN model performs very well on a real dataset, outperforming existing
approaches.

1

Introduction

Human activity recognition (HAR) is becoming extensively popular due to its abundant and far-reaching applications
in smart homes, monitoring, and surveillance. HAR offers valuable insights into a person’s physical functioning and
behavior, which can be automatically monitored to provide individualized assistance. With the advancement of Wi-Fi
technologies, individuals are now surrounded by devices capable of sensing and communication, which makes activity
identiﬁcation signiﬁcantly efﬁcient than image/video-based and wearable sensors-based approaches. More speciﬁcally,
there are several techniques to recognize human activities: one strategy employs camera-based techniques, which have
the drawbacks of requiring line of sight and suitable lighting conditions. Another strategy is using wearable sensors,
which are more accurate and straightforward, but inconvenient and costly Wang et al. [2015]. Both of these approaches
have the issue of potentially breaching personal privacy.

The use of Channel State Information (CSI) from Wi-Fi signals to detect human activity has developed rapidly in recent
years. CSI measurement is a ﬁne-grained metric that captures a Wi-Fi channel’s amplitude and phase variations at
distinct subcarrier levels. CSI is more stable than Received Signal Strength Indicator (RSSI); therefore, it is often the
preferable option for implementing HAR systems T. F. Sanam and H. Godrich [2020]. CSI signals allow us to observe
activity across walls and behind closed doors and detect basic motions or a sequence of gestures based on the properties
of signal penetration Adib and Katabi [2013]. Due to the unique capacity to decrease multipath effects, CSI signals
carry useful information for activity recognition. As such, modern Wi-Fi-based device-free HAR systems exploit
correlations between CSI signal changes and body motions Wang et al. [2018a]. However, only a limited number of
Wi-Fi receiving devices, such as Wi-Fi 5300 NICs, offer access to the CSI data Gu et al. [2015]. CSI tools Halperin
et al. [2011] have made it feasible to capture CSI data and explore the association between signals and human activities.

Preprint submitted to Elsevier

1.1 Related Works

In recent years, researchers have developed several methods for CSI-based activity recognition. Yang et al. proposed a
CSI signal enhancement method and antenna selection-based framework for human activity identiﬁcation Yang et al.
[2021]. Wang et al. proposed a channel selective activity recognition system (CSAR), where they showed how the
channel selection and the Long Short-Term Memory network (LSTM) can work together for HAR Wang et al. [2018b].
Gao et al. used a deep neural network to learn optimized deep features from radio images Gao et al. [2017]. Hsieh et
al. proposed a simple deep neural network for HAR Hsieh et al. [2021], that incorporates the Multi-Layer Perceptron
(MLP) and one-dimensional CNN (1D-CNN). Dayal et al. proposed a method with upgraded PCA technique and a
deep neural network Dayal et al. [2015]. Yang et al. designed an occupancy detection system based on the CSI to
demonstrate its effectiveness on the Internet of Things (IoT) platform Yang et al. [2018]. Another method that utilized
Recurrent Neural Networks (RNN) for activity recognition was proposed by Ding and Wang Ding and Wang [2019].
Modern generative adversarial networks (GAN) are also being used for HAR, see the work of Wang et al. Wang
et al. [2021], for example, which handled the problem of non-uniformly distributed unlabeled data with infrequently
performed actions. Aside from these, two noteworthy works are WiKey and WiGest. WiKey is a keystroke recognition
system proposed by Ali et al. Ali et al. [2015] and WiGest is a in-air hand gestures detection system proposed by
Abdelnasser et al. Abdelnasser et al. [2015] that employs the user’s mobile device.

Despite these advances in CSI-based activity recognition, there is still room for improvement in the robustness and
effectiveness of the multi-class classiﬁcation regime for HAR systems. More speciﬁcally, existing HAR systems have
limited practical real-time applicability as they are affected by the high dimensional data. Additionally, CSI-based
methods have their own set of difﬁculties and limitations. In this paper, we propose a unique approach to integrate
PCA-based dimensionality reduction, DWT-based feature extraction and a CNN-based multi-class classiﬁcation scheme
that is capable of identifying activities regardless of the physiological and behavioral aspects of the individual and
environmental elements, and is suitable for real-time applications.

1.2 Our Contributions

• In this study, the subcarrier fusion method applying Principal Component Analysis (PCA) and the approach

employing no fusion are explored.

• An adaptive activity segmentation algorithm is implemented, which minimizes segmentation error and adapts

the segmentation window to the data; imposing less constraints on the preprocessing.

• A novel HAR framework is proposed that integrates PCA-based dimensionality reduction, DWT-based feature

extraction and CNN-based classiﬁcation

• The proposed PCWCNN framework is contrasted to the baseline algorithms and contemporary HAR systems.
In order to determine the model’s robustness and ﬂexibility, its performance in varied indoor environments is
investigated.

2 Preliminaries

In this section, we describe the necessary preliminary concepts that are relevant for our proposed method.

2.1 Multipath Propagation Model

A radio signal transmitted from a stationary source will encounter random objects in an indoor environment, producing
replicas of the transmitted signal. When a single pulse is transmitted over a multipath channel, the received signal
appears as a pulse train, with each pulse corresponding to a line-of-sight component or a different multipath component
associated with different scatterers Goldsmith [2005]. Because of the surroundings, there is one primary path (Line-Of-
Sight, LOS) and multiple reﬂected paths (Non-Line-Of-Sight, NLOS). These NLOS components are duplicates of the
transmitted signal that have been reﬂected, diffracted, or scattered and can be reduced in power, delayed in time, and
phase and frequency displaced from the LOS signal path.

The Friis free space propagation model Wang et al. [2016] is used to model the path loss of line-of-sight (LOS) path in
a free space environment, applicable in the transmitting antenna’s far-ﬁeld region, and is based on the inverse square
law of distance. The model expresses the received power Pr(d) of a receiver antenna in terms of the distance d from a
radiating transmitter antenna in the free space:

Pr(d) =

PtGtGrλ2
(4π)2d2 ,

2

(1)

Preprint submitted to Elsevier

where Pt is the transmitted power, Gr denotes the receiving antenna gain, Gt denotes the transmitter antenna gain, λ
denotes the wavelength in meters and d denotes the distance from the transmitter to a receiver in meters Wang et al.
[2016].

Figure 1: Static and dynamic components of the multipath in an indoor environment caused by human activities

Let, s(t) denote the transmitted signal as:

s(t) = (cid:60)

a(t)ej(2πfct+φ0)(cid:111)
(cid:110)

,

(2)

where a(t) is the time-varying complex-valued amplitude, fc is the carrier frequency. Then the total received signal is
calculated as the sum of the LOS path and all the multipath components, and can be shown as:

r(t) = (cid:60)






N (t)
(cid:88)





n=0

αn(t)e−jφn(t)a (t − τn(t))


 ej2πfct






,

(3)

where n = 0 represents the LOS path. The number of resolvable multipath components, the multipath delay, the
amplitude, and the phase shift due to the nth multipath are denoted by N (t), τn(t), αn(t), and φn(t), respectively.
Let’s consider an indoor stationary environment where the objects are ﬁxed. The expected values of the variables in the
equation (3) will be time-invariant, assuming a(t) is also time-invariant, as:

A(t) =

N (t)
(cid:88)

n=0

αn(t)e−jφn(t)a (t − τn(t)) .

(4)

If an object is in motion in the environment, the multipath reﬂected or scattered from that object will have time-varying
amplitudes. Let the multipath components corresponding to n ∈ S have time-varying amplitudes. It can be shown
that A(t) = AS + AD(t), the received signal amplitude will be the sum of two components: the time-invariant static
component, AS, and the time-varying dynamic component AD. The dynamic component will capture any motion
occurring in the indoor environment. Therefore, the received CSI data will have both a static and a dynamic component.
By focusing on the dynamic components at various subcarrier or frequency levels, it is possible to determine the
association between the variation in human activity speed and the CSI dynamics.

2.2 Overview of MIMO-OFDM Channel

Figure 2: CSI data of different Antennas

3

Preprint submitted to Elsevier

Figure 3: CWT Scalogram of different activities

An array of several transmit or receive antennas is used in a Multiple Input Multiple Output (MIMO) communication
system, where the array members are separated by distance. The same information is delivered across different fading
channels. This is a strategy for increasing spatial diversity. If there are NT transmit and NR receive antennas, then
NR × NT independent fading paths are available. The input-output relation of such a MIMO channel can be written as:

y = Hs + n,

(5)

where H is an NR × NT channel matrix, n is the spatially and temporally white Zero-Mean Circulant Symmetric
Complex Gaussian (ZMCSCG) noise vector with equal variance in each dimension, and s is the transmitted signal.

On the other hand, Orthogonal Frequency Division Multiplexing (OFDM) is a multicarrier modulation technology
using densely spaced orthogonal subcarriers. Each of these subcarriers stands for a narrow-band ﬂat fading channel. In
the IEEE 802.11n standard, the CSI of an OFDM system provide amplitude and phase information for each subcarrier
level T. F. Sanam and H. Godrich [2020], T. F. Sanam and H. Godrich [2019].

2.3 Channel State Information (CSI)

Received Signal Strength Indicator (RSSI) and Channel State Information (CSI) are the two components of Wi-Fi
signals. RSSI is the total energy of all signal channels combined, whereas CSI characterizes the properties of the
wireless propagation channel between the transmitter and the receiver. Because of multipath fading and background
noise, RSSI measurements change over time and are therefore somewhat unreliable. On the other hand, CSI amplitude
values exhibit signiﬁcant consistency over time at a given point T. F. Sanam and H. Godrich [2020], Sanam and Godrich
[2018]. As mentioned before, the multipath propagation causes a delay spread in the time domain and selective fading
in the frequency domain. These effects are incorporated in CSI, exhibiting channel selective fading on several subcarrier
levels. The frequency response of the channel corresponding to each subcarrier can be expressed as:

H(k) = |H(k)|ej∠H(k),
(6)
where H(k) denotes the CSI of kth subcarrier, |H(k)| denotes the amplitude of the kth subcarrier, and ∠H(k) denotes
the phase.

CSI data can be extracted at the receiver as a NT × NR × NS matrix, where NT is the number of transmitting antennae,
NR is the number of receiving antennae, and NS is the number of OFDM subcarriers. More speciﬁcally, CSI data can
be expressed as:

CSI 1 = [CSI 1,1, CSI 1,2, . . . , CSI 1,NS ]
CSI 2 = [CSI 2,1, CSI 2,2, . . . , CSI 2,NS ]

...

CSI K = [CSI K,1, CSI K,2, . . . , CSI K,NS ],

where K = NRNT is the number of streams present for each transmitter-receiver pair. Each pair contains a NS number
of subcarriers, so the total number of CSI streams is NT NRNS. Fig. 2 shows the raw CSI data for a particular activity –

4

Preprint submitted to Elsevier

bending. The activity data consist of three-receiver antenna data, each of which further consists of 30 subcarrier data (20
subcarrier data has been plotted for simplicity). We observed that some antennas are more insensitive to some activity
and as such, the CSI response of an insensitive antenna is not quite useful for activity recognition. Since the wireless
channel is a frequency selective fading channel, different frequencies show different responses to the same activity.
Therefore, CSI for each subcarrier is different. In general, subcarriers of low frequencies are less responsive to the
activity, whereas subcarriers of high frequencies are more responsive T. F. Sanam and H. Godrich [2018]. Moreover, low-
frequency subcarriers are more prone to noise compared to high-frequency ones. If we arbitrarily choose a subcarrier
for the purpose of HAR, the recognition performance may not be good. Therefore, further analysis is necessary for
merging these subcarriers to remove redundancy, reduce noise and preserve maximum activity information.

In an ideal situation, if a particular activity is considered for the same antenna and subcarrier, Wi-Fi CSI data should not
differ much for different volunteers. But in practice, CSI data depends on many factors relating to the subject, namely
the body shape, height, duration of activity performed, etc. Also, each individual’s time to complete a particular activity
is different.

The objective of human activity recognition system modeling is to generate a robust system resilient to changes to
the system, i.e., environmental changes, different subjects, etc. In an indoor environment, the Channel Frequency
Response (CFR) is a linear combination of multipath components reﬂected off objects in the environment, including
the subject’s body Wang et al. [2015]. Thus, CSI data amplitude variation and phase change signiﬁcantly depend on
the surrounding environment. Therefore, it is crucial to distinguish the change in speed of the multipath components
of each activity irrespective of the background and subject. Environmental changes signiﬁcantly dominate statistical
features. Time-Frequency analysis tools, such as Short-Time Fourier Transform (STFT) or Discrete Wavelet Transform
(DWT), relate to the speed of the multipath changes Wang et al. [2015]. Fig. 3 shows Continuous Wavelet Transform
(CWT) scalogram for three activities. CWT has been chosen since it provides high-resolution analysis capability. These
CWT scalograms can be considered a ﬁngerprint of the activity being performed. In the scalogram of horizontal arm
wave, there are high-frequency components of around 8 Hz and 12 Hz in 4-8 s time slot. For bend activity, signiﬁcant
low-frequency components in 2-5 s indicate the slow torso movement. Since upper body movement is also present,
there are few high-frequency components. On the other hand, for the last activity, squat, there are only low-frequency
components in 2-5 s, indicating slow lower body movement. The sampling rate of WiAR CSI data was 30 Hz. So the
highest frequency to show on the scalogram is Nyquist frequency 15 Hz.

The primary challenge with CSI-based activity recognition is that CSI data contains noise, making it difﬁcult to use any
detection system directly on the raw data. To eliminate these artifacts, several pre-processing strategies are required.
The second challenge is choosing a proper feature extraction approach. For the same activity, different individuals need
varying times- pans. The duration of an activity might change over time, even for the same individual. Moreover, a
segmentation task is required to identify the activity part; however, inaccurate segmentation may lead to low accuracy.
This study proposes a technique that addresses these issues and yields acceptable outcomes.

2.4 Residual Networks and Dense Convolutional Networks

Resnets He et al. [2016] provided a feedforward neural network implementation with "shortcut connections" or "skip
connections," bypassing one or more layers when deeper networks may start converging. This approach addresses the
issue of loss or saturation of accuracy as network depth increases. Deeper networks, even with shortcut connections,
face the difﬁculty of quickly disappearing information about the input and gradient as it propagates through the
networks Fujieda et al. [2018]. To overcome this issue, Dense Convolutional Network (DenseNet) Huang et al. [2017]
incorporates shortcut connections connecting each layer to its preceding layers. Through channel-wise concatenation,
dense connections allow each level of deconstructed signal to be directly coupled with all following levels. With this
connection, the network can effectively route all information from the input side to the output side.

3 System Overview

Our proposed PCWCNN system framework is presented in Fig. 4. The modules that are included in this system are the
CSI Data Extraction module, Subcarrier Fusion (SF) module, Savitzky-Golay Filter, Adaptive Activity Segmentation
module, and PCWCNN model. We describe each of these components below.

3.1 Subcarrier Fusion (SF) Module

The authors in Wang et al. [2015] developed a way of applying PCA to CSI streams to solve the problem of integrating
CSI streams and reducing noise since typical frequency domain ﬁlters are ineffective. The steps involving this method

5

Preprint submitted to Elsevier

Figure 4: Framework of PCWCNN activity recognition system

are ﬁnding the correlations between CSI streams, performing an Eigen decomposition, and determining the principal
components.
Let Xi denote the ith CSI stream (ith subcarrier of the CSI data. We can arrange all the CSI streams column-wise
to form the matrix as X = [X1, X2, X3, · · · , XN]. We can ﬁnd the correlation estimate from the auto-correlation
matrix R = XT X ∈ RN ×N . As the Eigenvectors of an auto-correlation matrix are orthogonal to each other, it is
possible to project the data on the eigenvectors to ﬁnd the components in their signal subspace. The kth principal
component can be constructed as hk = Rvk. If we arrange the eigenvectors according to the decreasing order of
their corresponding eigenvalues, then the smallest few eigenvalues will be associated with the noise and the principal
components corresponding to these eigenvalues can be ignored. This will effectively ﬁlter out a portion of the noise.
Discarding these principal components will also result in dimensionality reduction. Additionally, the ﬁrst principal
component has the largest possible variance. Although the ﬁrst principal component captures most of the data variability,
it simultaneously captures the burst noise in all the CSI streams. As discussed in Wang et al. [2015], noises caused
by internal state changes are most prominently present in the ﬁrst principal component. Therefore, we discard the
ﬁrst principal component and utilize the second and third principal components in our method. The selected principal
components will be subjected to further processing and denoising using Savitzkey-Golay Filter.

3.2 Savitzkey-Golay Filter

Savitzky and Golay Savitzky and Golay [1964] presented a data smoothing method based on local least-squares
polynomial approximation. They demonstrated that discrete convolution with a ﬁxed impulse response is similar to
ﬁtting a polynomial to a set of input samples and then evaluating the resultant polynomial at a single point inside
the approximation interval. The low pass ﬁlters obtained by this method are known as Savitzky-Golay ﬁlters Schafer
[2011].

A set of 2M + 1 input samples within the approximation interval are effectively combined by a ﬁxed set of weighting
coefﬁcients that can be computed once for a given polynomial order N and approximation interval with a length of
2M + 1. If ˜p[n] is the polynomial ﬁt to the unit impulse evaluated at the integers −M ≤ n ≤ M , then

˜p[n] =

N
(cid:88)

k=0

˜aknk,

(7)

where,

(8)
, d = [0, 0, ..., 0, 1, 0, ..., 0, 0]T is a (2M + 1) × 1 column vector impulse and AT is the (N + 1) × (2M + 1) matrix:

˜a = (cid:0)AT A(cid:1)−1

AT d,

AT =










(−M )0
(−M )1
(−M )2
...

· · ·
· · ·
· · ·
...
(−M )N · · ·

(−1)0
1
(−1)1
0
(−1)2
0
...
...
(−1)N 0

6

· · · M 0
· · · M 1
· · · M 2
...

10
11
12
...
· · ·
1N · · · M N .










(9)

Preprint submitted to Elsevier

The impulse response of the ﬁlter is:

h[−n] = ˜p[n].

(10)

Figure 5: Activity detection network of the proposed PCWCNN framework: This network provides a three-level multi-resolution
decomposition of both principal components. Deep CNN is used, which consists of convolution layers with 3 × 1 kernels. To
minimize feature map dimensions, 3 × 1 convolutional kernels, a stride of 2 and 1 × 1 padding are employed. The level J
approximation coefﬁcient W J
φ and the convolutional layers are channel-wise concatenated at each stage. Conv is followed by a
number indicating the number of output channels. Global average pooling followed by ﬂattening is implemented, which is then
followed by a fully connected layer (FCNN). The last layer is the softmax layer, which generates activity class estimates.

3.3 Adaptive Activity Segmentation

The precise segmentation of the activity part from CSI data is a challenging aspect of activity recognition. Activity
segmentation is necessary to distinguish the dynamic activity segment from the static non-activity section. Non-activity
data is excluded from the recognition process for improved efﬁciency since it contains no information about the activity.
To that end, a sliding window-based segmentation algorithm is proposed in Yang et al. [2021]. It ﬁnds an array of the
mean-variance of raw CSI data and ﬁlters out the part lower than a threshold corresponding to the third quartile of the
sorted variance values. There are certain limitations to such an approach. Some activities may be erroneously segmented
with a non-adaptive window since they are performed for a different duration. Some activities may last longer than the
segmented window, whereas others may be of less duration. As a result, an adaptive algorithm is required to modify
the threshold value according to the nature of the signal. A modiﬁed sliding window-based segmentation process has
been used to solve this issue. After the sliding window is applied to the denoised principal components, the variance in
that window is computed and saved in V. Then, the sliding window is shifted across V, and the mean in that window
is calculated and stored in M. The values of M are sorted and the maximum value is obtained. A threshold value
T = p × max (M) is computed where 0 < p < 1, and the values in M less than T are discarded. Value of p is set such
that the segmentation length t, normalized to the length of the CSI data sequence is greater than some preﬁxed value t1
and less than t2, and 0 < t1 < t < t2 < 1. In this work, the value of the parameters t1 and t2 were selected to be 0.3
and 0.5, respectively. The value of normalized segment length t is minimized in an iterative manner. The start time and
end time of the activity segment are obtained from the ﬁltered M. Once the segmented activity parts of PC2 and PC3
have been obtained, activity recognition followed by feature extraction is performed.

7

Preprint submitted to Elsevier

3.4 DWT-Based Feature Extraction

Because the statistics of CSI signal frequency vary with time, CSI activity signal can be better represented on a
time-frequency domain concurrently. To that end, we use the Discrete Wavelet Transform (DWT) in this work. The
DWT, is a computationally efﬁcient approach for extracting information from non-stationary signals. In contrast to
the Short-time Fourier Transform (STFT), which provides uniform time resolution across all frequencies, DWT offers
high time resolution and low-frequency resolution for high frequencies and high-frequency resolution and low time
resolution for low frequencies Tzanetakis et al. [2001]. The DWT coefﬁcients of a discrete sequence x(n) can be
written as

Wφ(j0, k) =

Wψ(j, k) =

1
√
N

1
√
N

(cid:88)

x(n)φj0,k(n),

n
(cid:88)

n

x(n)ψj,k(n)

f or j ≥ j0.

(11)

(12)

Here, φ(j0, k) is the scaling basis function and ψ(j, k) is the wavelet basis function. Generally, j0 is set to be 0 and
N to be a power of 2, which is the length of the discrete sequence x(n). The approximation coefﬁcients are obtained
by the convolution of the input signal x(n) with the scaling ﬁlter, followed by dyadic decimation. Similarly, the
detail coefﬁcients are obtained by the convolution of the input signal x(n) with the wavelet ﬁlter, followed by dyadic
decimation:

Wψ(j, k) =

Wφ(j, k) =

(cid:88)

n
(cid:88)

n

hψ(n − 2k)Wφ(j + 1, n),

hφ(n − 2k)Wφ(j + 1, n),

(13)

(14)

where Wφ(j, k) and Wψ(j, k) are the level j approximation and detail coefﬁcients, and hφ(n) and hψ(n) are the scaling
and wavelet ﬁlters.

3.5 Activity Recognition

Fujieda et al. Fujieda et al. [2018] proposed Wavelet Convolutional Neural Network (Wavelet CNN); they demonstrated
that wavelet CNNs produce comparable, if not better, accuracies with a substantially fewer trainable parameter than
conventional CNNs. Wavelet CNN, or WCNN, is thus less complicated to implement and is more suitable for real-time
applications. Furthermore, it is less susceptible to over-ﬁtting and consumes less memory than a typical CNN. WCNN
is inﬂuenced by well-known architectures such as Residual Networks (ResNets) and Dense Convolutional Networks
(DenseNets).

3.6 Summary of the Proposed System

Following the PCA and organizing the Eigenvectors in decreasing order of their associated eigenvalues, the ﬁrst
principal component and those corresponding to lesser eigenvalues were removed in the SF module. Discarding these
unwanted principal components and keeping only the second and third principal components, dimensionality reduction
was achieved along with noise reduction. One activity sample from the dataset used in this study yielded a CSI with 90
subcarriers, of which only two principal components remained following subcarrier fusion.

In this work, we propose a modiﬁed WCNN network, namely the Principal Component-based Wavelet Convolutional
Neural Network (PCWCNN). This model takes the second and third principal components from the SF module and
feeds them into the WCNN, and a three-level multi-resolution decomposition of both principal components is performed.
The lower resolution counterpart of the DWT output captures the bulk of the original signal since the information in the
ﬁne-grained signal is typically sparse. As a result, the low-frequency version or approximation coefﬁcients of the DWT
output are used throughout this network.

The original principal components are concatenated and fed as input into a deep CNN network. The approximation
coefﬁcients from one step of the wavelet transformation are iteratively passed through multiple identical transformations
to yield various frequency renditions of the original principal components. Using the feature concatenation method,
the approximation coefﬁcients of these stages are combined with the feature maps of the convolutional layers across
the CNN. The CNN consists of convolution layers with 3 × 1 kernels. To minimize feature map dimensions, 3 × 1
convolutional kernels, a stride of 2 and 1×1 padding are employed. Incorporating the ResNet and Densenet architectures,
along with wavelet decomposition, may signiﬁcantly improve the recognition accuracy of a deep CNN Fujieda et al.
[2018]. Because DWT inherently comprises a decimation of the input signal, the approximation coefﬁcient size must be

8

Preprint submitted to Elsevier

analogous to that of the feature maps of the convolutional layers across the CNN to employ the feature concatenation
approach. A method can be used that employs 1 × 1 padding with a stride of 2 to halve the output to the size of the input
layer Fujieda et al. [2018]. Without reducing accuracy, this strategy may be used instead of max-pooling Springenberg
et al. [2015], Fujieda et al. [2018]. We used global average pooling followed by ﬂattening, which is then followed by a
fully connected layer (FCNN). The softmax layer generates activity class estimates.

4

Implementation and Evaluation

This section describes the proposed model’s implementation and evaluation compared to reference models. This
study used the WiAR data set Guo et al. [2019] for activity recognition leveraging Wi-Fi CSI data. This is a publicly
accessible data set that focuses on different types of activities and environments. WiAR gathers Wi-Fi CSI data from
three locations. The performance of the recognition method is inﬂuenced by the environment in which it is implemented.
The WiAR dataset comprises sixteen activities that may be grouped into three major categories based on the body parts
associated: upper body, lower body, and entire body activities. Upper body activities are those in which volunteers do
the task primarily with their upper skeleton joints. Lower-body movements only move the lower skeleton joints, entire
body activities combine upper and lower body activities. The data set is more diverse when there are multiple forms of
categorization. WiAR dataset acquired more than 7s of data for each activity sample, which includes 2-3s of activity
data and 4-6s of no-activity data (static component from the environment). In general, it takes a volunteer about 2-3
seconds to complete an activity at a moderate pace.

4.1 Data Acquisition

Figure 6: Performance comparison of different approaches on an individual employing (a) all subcarriers (b) subcarrier fusion

(a)

(b)

Table 1
Precision, Recall and F1-Score comparison of different approaches on one volunteer employing SF module
and DWT feature extraction.

Activity
Class
01
02
03
04
05
06
07
08
09
10
11
12
13
14
15
16

SVM
Precision Recall
1.00
0.67
1.00
1.00
1.00
0.33
1.00
1.00
0.67
1.00
1.00
1.00
0.67
1.00
0.67
1.00

1.00
1.00
1.00
1.00
0.75
0.33
1.00
0.75
1.00
0.75
1.00
1.00
1.00
0.75
1.00
1.00

F1-Score
1.00
0.80
1.00
1.00
0.86
0.33
1.00
0.86
0.80
0.86
1.00
1.00
0.80
0.86
0.80
1.00

RF

Precision Recall
1.00
0.33
1.00
0.67
0.67
0.67
1.00
0.67
0.67
1.00
1.00
1.00
1.00
1.00
1.00
1.00

0.75
1.00
1.00
1.00
0.67
0.67
1.00
0.67
0.67
0.75
1.00
1.00
1.00
0.75
1.00
1.00

F1-Score
0.86
0.50
1.00
0.80
0.67
0.67
1.00
0.67
0.67
0.86
1.00
1.00
1.00
0.86
1.00
1.00

KNN
Precision Recall
1.00
0.67
0.67
1.00
0.33
0.67
1.00
1.00
0.67
1.00
1.00
0.67
1.00
1.00
0.67
1.00

1.00
1.00
1.00
0.75
1.00
0.67
0.60
0.75
1.00
1.00
1.00
1.00
1.00
0.75
0.50
1.00

F1-Score
1.00
0.80
0.80
0.86
0.50
0.67
0.75
0.86
0.80
1.00
1.00
0.80
1.00
0.86
0.57
1.00

CNN
Precision Recall
1.00
1.00
1.00
1.00
0.67
1.00
1.00
1.00
1.00
1.00
1.00
1.00
1.00
1.00
0.67
1.00

1.00
1.00
1.00
1.00
1.00
0.75
1.00
0.75
1.00
1.00
1.00
1.00
1.00
1.00
1.00
1.00

F1-Score
1.00
1.00
1.00
1.00
0.80
0.86
1.00
0.86
1.00
1.00
1.00
1.00
1.00
1.00
0.80
1.00

WiAR collected activity data on two T400 laptops using the Intel 5300 NIC. The CSI tool that was developed Halperin
et al. [2011] was employed. One T400 laptop with one antenna transmits outbound signal data, while another with three

9

Preprint submitted to Elsevier

antennas receives signal data from multiple paths upon reﬂection. The volunteers were placed in between these two
computers to do their activities. The 802.11n NIC cards monitor the channel integrity for each packet that it receives.
The CSI is then transmitted to a user-space program for processing by the driver. The Intel 5300 NIC delivers CSI for
30 bands of subcarriers, which are evenly divided across the 56 subcarriers of a 20 MHz channel or the 114 carriers of a
40 MHz channel Halperin et al. [2011].

4.2 Different Factors

The frequencies used among commercial Wi-Fi systems range from 2.4GHz to 5GHz. WiAR used 20MHz bandwidth
with 30 subcarriers at 5GHz, which provides higher stability than 2.4GHz. WiAR obtained CSI data for a single
transmitter antenna and three receiver antennas. The use of multiple antennas extends the range of the Wi-Fi data
communication system, but it still introduces complications in the detection process. Despite the additional challenges,
data from multiple antennas gives more information than just a single antenna transmitter-receiver system, enhancing
the recognition system.

Ten volunteers carry out all activities for added robustness. Because different individuals need varying amounts of time
to complete their activities, having a large dataset of volunteers is essential. Also, the body’s shape, height, and pattern
of activity are all essential factors in the recognition procedure. WiAR collected 30 samples from each of the volunteers.
As indicated Guo et al. [2019], the effect of volunteers on CSI data is examined in terms of sex, height, weight, and
experience.

WiAR created three distance levels to investigate the effects of different distances between the transmitter and the
receiver on human activity recognition. The distance factor data is collected for three distances; the three distances are 1
m, 3 m, and 6 m. The hall served as the experimental setting, and the environment was more challenging owing to the
combination of glass walls and elevators. WiAR also created three levels for the height between the receiver and the
ﬂoor to assess the inﬂuence of varying heights on human activity recognition. The measurements are 60 cm, 90 cm, and
120 cm, respectively.

4.3 Performance Analysis

(a)

(b)

(c)

Figure 7: Performance comparison of different combinations of principal components (PCs) using DWT feature extraction and
1D-CNN for one individual

A few reference models (SVM, RF, CNN) are compared to the proposed PCWCNN framework. Support Vector
Machine (SVM) is a supervised nonparametric algorithm that performs effectively with high-dimensional feature
spaces. The Random Forest algorithm combines several randomized decision trees and aggregates their predictions to
produce a robust learner. For RF, the classiﬁer’s number of trees was set to 200, and the maximum depth was set to 20.
Convolution Neural Network (CNN) is a commonly deployed DL technique that includes shift-invariance, which is
crucial since the activity segment might occur at any moment. One of the difﬁculties in employing CNNs is that the CSI
signal recorded from the experiments may have a variable duration. Zero padding is one method of getting around the
CNN input layer’s limitation. This study uses a One-dimensional Convolutional Neural Network (1D-CNN) model. The
model involves a 384-element vector as input and outputs a vector containing probabilities for each potential activity
type. Before training the models, 20% of the data was reserved as the test set, and the rest was used for training.

Fig. 6 shows a performance comparison of the reference models for two cases: using all the subcarriers and using
subcarrier fusion. The performance disparity between the two methods is negligible. It can be argued that the PCA-based
subcarrier fusion approach is more appropriate in terms of efﬁciency with little to no performance sacriﬁce given the
subcarrier fusion method’s strength in dimensionality reduction. Table 1 compares the accuracy, recall, and F1-score
of different approaches for one volunteer using subcarrier fusion. The accuracy of the PCA-based subcarrier fusion

10

PC-1PC-1,2PC-1,2,3PC-2,3PrincipalComponents707580859095100Accuracy(%)88%92%92%96%PC-1-2PC-2,3PC-3,4PC-4,5PrincipalComponents707580859095100Accuracy(%)92%96%83%75%PC-2,3PC-1,2,3PC-2,3,4PC-2,3,5PrincipalComponents707580859095100Accuracy(%)96%92%88%88%Preprint submitted to Elsevier

Table 2
Overall Performance of PCWCNN approach
Activity Class
01. Horizontal Arm Wave
02. High Arm Wave
03. Two Hands Wave
04. High Throw
05. Draw X
06. Draw Tick
07. Toss Paper
08. Forward Kick
09. Side Kick
10. Bend
11. Hand Clap
12. Walk
13. Phone Call
14. Drink Water
15. Sit Down
16. Squat
Macro Average

Precision Recall
1.00
0.89
1.00
0.89
1.00
1.00
1.00
0.94
0.94
1.00
0.94
0.94
0.89
0.89
1.00
0.94
0.95

1.00
1.00
0.95
1.00
0.90
1.00
0.82
0.85
1.00
1.00
1.00
1.00
1.00
0.94
0.90
1.00
0.96

F1-Score
1.00
0.94
0.97
0.94
0.95
1.00
0.90
0.89
0.97
1.00
0.97
0.97
0.94
0.91
0.95
0.97
0.96

Table 3
Recognition accuracy comparison of different approaches

Recognition
Approach
CARM
LCED
WiFall
PCWCNN

Number of
Volunteers
25
10
10
10

Number of
Activities
8
16
4
16

Recognition
Accuracy
96.00%
95.00%
94.00%
95.50%

Figure 8: Confusion matrix generated from PCWCNN approach

method using CNN is 96%, compared to 94% for the all subcarriers method. SVM and RF perform similarly in both
cases, however KNN performance degrades when using the subcarrier fusion method.

The performance comparison of several principal component groupings is demonstrated in Fig. 7. We applied a
1D-CNN network together with DWT-based feature extraction to illustrate this comparison. The effect of combining

11

HorizontalArmWaveHighArmWaveTwoHandsWaveHighThrowDrawXDrawTickTossPaperForwardKickSideKickBendHandClapWalkPhoneCallDrinkWaterSitDownSquatPredictedlabelHorizontalArmWaveHighArmWaveTwoHandsWaveHighThrowDrawXDrawTickTossPaperForwardKickSideKickBendHandClapWalkPhoneCallDrinkWaterSitDownSquatTruelabel1.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.890.060.000.000.000.000.000.000.000.000.000.000.000.060.000.000.001.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.890.060.000.060.000.000.000.000.000.000.000.000.000.000.000.000.001.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.001.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.001.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.940.000.000.000.000.000.000.060.000.000.000.000.000.000.000.000.060.940.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.001.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.940.000.000.060.000.000.000.000.000.000.060.000.000.000.000.000.000.940.000.000.000.000.000.000.000.000.000.000.060.060.000.000.000.000.890.000.000.000.000.000.000.000.000.000.110.000.000.000.000.000.000.890.000.000.000.000.000.000.000.000.000.000.000.000.000.000.000.001.000.000.000.000.000.000.000.000.000.060.000.000.000.000.000.000.000.94Preprint submitted to Elsevier

(a) Effect of distance

(b) Effect of height

Figure 9: Effect of distance and height on PCWCNN

the ﬁrst principal component (PC1) with other components is depicted in Fig. 7a. It is obvious that the ﬁrst principal
component is insufﬁcient. The accuracy improves from 88% to 92% when PC2 or PC3 are integrated with PC1.
However, PC2 and PC3 pair performs signiﬁcantly better than any other combination that includes PC1. Comparisons
between several PC pairings are shown in Fig. 7b. Evidently, PC-2,3 pair outperforms others. PC-4,5 pair performs
much worse (75%), which points to noise in the later-end PCs. Fig. 7c compares the performance of combining various
PCs with PC-2,3. Performance always degrades regardless of which PC is added to the pair PC-2,3. The rationale for
using the PC-2,3 combination in our proposed PCWCNN model is demonstrated by this comparison study.

The accuracy, recall, and F1-score of all the volunteers using the proposed PCWCNN technique are shown in Table 2.
The results show the superiority of this method over previous reference models. Fig. 8 depicts the approach’s confusion
matrix. Whereas the majority of activities were competently recognized, the detection accuracy of some of them was
low (89%), which might be attributed to similarities between them or related activities. High arm waves, high throw,
phone call, and drink water are all upper body activities. Although these activities can be identiﬁed visually, using
CSI alone would make it substantially more challenging. Additionally, the activity patterns of these activities are very
dependent on the speciﬁc individual. Therefore, in comparison, the detection accuracy of these activities is somewhat
lower. Moreover, compared to the results obtained for one volunteer, the overall performance ﬁndings demonstrate a
considerable performance decline. The reasoning can be deduced due to some individuals’ poor quality data and the
system becoming more complex due to the inclusion of more volunteers.

Table 3 compares the accuracy of the methodologies described in previous literature, as well as a synopsis of the dataset
that was used. In terms of accuracy, the PCWCNN method yields promising results, with accuracy surpassing 95%.
Because additional classes of activities complicate the problem, the best analogy is the LCED technique, which has a
95% overall accuracy.

4.4 Effect of Distance and Height for PCWCNN

The performance of the proposed PCWCNN technique for various distance and height data is shown in Fig. 9. The
distance factor data is collected for three distances: 1 m, 3 m, and 6 m. The results outperform reference models
considerably. Performance for 6m data is the best for distance factor data. But Wi-Fi signals have a transmission range
of fewer than 15 meters and a detecting range of fewer than 5 meters Guo et al. [2021]. Therefore the results obtained
are contradictory to the general idea.

Since different height data correlates to various body sections, the WiAR dataset provides various height data. The
lower body corresponds to 60 cm in height. The whole body corresponds to 90 cm. Upper-body activities correlate to a
height of 120 cm. Regarding height factor data, the highest performance comes from 90 cm data, which can be linked
to the fact that at this height, all activities relating to all heights are given equal attention.

5 Conclusion

In this paper, we proposed a novel human activity recognition method that is accurate and robust for real-time
applications. We achieved this by employing an adaptive activity segmentation algorithm, PCA- and DWT-based
preprocessing and CNN-based classiﬁcation. We performed extensive experimentation on a real dataset, and empirically
compared the performance of our method against several recent approaches. We demonstrated that our method
comfortably outperforms the existing ones. An interesting future work could be enhancing the resilience of our

12

SVMRFCNNPCWCNN020406080100Performance(%)1m3m6mSVMRFCNNPCWCNN020406080100Performance(%)60cm90cm120cmPreprint submitted to Elsevier

proposed method against environmental changes. Another direction could be incorporating formal privacy guarantees
in our method, as CSI data correlated with human movement is potentially privacy-sensitive.

References

Wei Wang, Alex X Liu, Muhammad Shahzad, Kang Ling, and Sanglu Lu. Understanding and modeling of wiﬁ signal
based human activity recognition. In Proceedings of the 21st Annual International Conference on Mobile Computing
and Networking, pages 65–76, 2015.

T. F. Sanam and H. Godrich. A multi-view discriminant learning approach for indoor localization using amplitude and

phase features of csi. IEEE Access, 8:59947–59959, 2020.

Fadel Adib and Dina Katabi. See through walls with wiﬁ! In Proceedings of the ACM SIGCOMM 2013 conference on

SIGCOMM, pages 75–86, 2013.

Fangxin Wang, Wei Gong, and Jiangchuan Liu. On spatial diversity in wiﬁ-based human activity recognition: A deep

learning-based approach. IEEE Internet of Things Journal, 6(2):2035–2047, 2018a.

Yu Gu, Fuji Ren, and Jie Li. Paws: Passive human activity recognition based on wiﬁ ambient signals. IEEE Internet of

Things Journal, 3(5):796–805, 2015.

Daniel Halperin, Wenjun Hu, Anmol Sheth, and David Wetherall. Tool release: Gathering 802.11 n traces with channel

state information. ACM SIGCOMM Computer Communication Review, 41(1):53–53, 2011.

Jieming Yang, Yanming Liu, Zhiying Liu, Yun Wu, Tianyang Li, and Yuehua Yang. A framework for human activity
recognition based on wiﬁ csi signal enhancement. International Journal of Antennas and Propagation, 2021, 2021.
Fangxin Wang, Wei Gong, Jiangchuan Liu, and Kui Wu. Channel selective activity recognition with wiﬁ: A deep
learning approach exploring wideband information. IEEE Transactions on Network Science and Engineering, 7(1):
181–192, 2018b.

Qinhua Gao, Jie Wang, Xiaorui Ma, Xueyan Feng, and Hongyu Wang. Csi-based device-free wireless localization and
activity recognition using radio image features. IEEE Transactions on Vehicular Technology, 66(11):10346–10356,
2017.

Chaur-Heh Hsieh, Jen-Yang Chen, Chung-Ming Kuo, and Ping Wang. End-to-end deep learning-based human activity

recognition using channel state information. Journal of Internet Technology, 22(2):271–281, 2021.

Sankalp Dayal, Hirokazu Narui, and Paraskevas Deligiannis. Human fall detection in indoor environments using

channel state information of wi-ﬁ signals, 2015.

Jianfei Yang, Han Zou, Hao Jiang, and Lihua Xie. Device-free occupant activity sensing using wiﬁ-enabled iot devices

for smart homes. IEEE Internet of Things Journal, 5(5):3991–4002, 2018.

Jianyang Ding and Yong Wang. Wiﬁ csi-based human activity recognition using deep recurrent neural network. IEEE

Access, 7:174257–174269, 2019.

Dazhuo Wang, Jianfei Yang, Wei Cui, Lihua Xie, and Sumei Sun. Multimodal csi-based human activity recognition

using gans. IEEE Internet of Things Journal, 8(24):17345–17355, 2021.

Kamran Ali, Alex X Liu, Wei Wang, and Muhammad Shahzad. Keystroke recognition using wiﬁ signals. In Proceedings

of the 21st Annual International Conference on Mobile Computing and Networking, pages 90–102, 2015.

Heba Abdelnasser, Moustafa Youssef, and Khaled A Harras. Wigest: A ubiquitous wiﬁ-based gesture recognition
system. In 2015 IEEE Conference on Computer Communications (INFOCOM), pages 1472–1480. IEEE, 2015.
Andrea Goldsmith. Wireless Communications, chapter Statistical Multipath Channel Models, pages 65–69. Cambridge

university press, New York, 2005.

Yuxi Wang, Kaishun Wu, and Lionel M Ni. Wifall: Device-free fall detection by wireless networks. IEEE Transactions

on Mobile Computing, 16(2):581–594, 2016.

T. F. Sanam and H. Godrich. Fuseloc: A cca based information fusion for indoor localization using csi phase and
amplitude of wiﬁ signals. In ICASSP 2019-2019 IEEE International Conference on Acoustics, Speech and Signal
Processing (ICASSP), pages 7565–7569. IEEE, 2019.

T. F. Sanam and H. Godrich. Comute: A convolutional neural network based device free multiple target localization

using csi. arXiv preprint arXiv:2003.05734, 2020.

Tahsina Farah Sanam and Hana Godrich. Device free indoor localization using discriminant features of csi a canonical
correlation paradigm. In 2018 52nd Asilomar Conference on Signals, Systems, and Computers, pages 423–427. IEEE,
2018.

13

Preprint submitted to Elsevier

T. F. Sanam and H. Godrich. An improved csi based device free indoor localization using machine learning based
classiﬁcation approach. In 2018 26th European Signal Processing Conference (EUSIPCO), pages 2390–2394. IEEE,
2018.

Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. Deep residual learning for image recognition. In Proceedings

of the IEEE Conference on Computer Vision and Pattern Recognition, pages 770–778, 2016.

Shin Fujieda, Kohei Takayama, and Toshiya Hachisuka. Wavelet convolutional neural networks. arXiv preprint

arXiv:1805.08620, 2018.

Gao Huang, Zhuang Liu, Laurens Van Der Maaten, and Kilian Q Weinberger. Densely connected convolutional
networks. In Proceedings of the IEEE conference on Computer Vision and Pattern Recognition, pages 4700–4708,
2017.

Abraham Savitzky and Marcel JE Golay. Smoothing and differentiation of data by simpliﬁed least squares procedures.

Analytical chemistry, 36(8):1627–1639, 1964.

Ronald W Schafer. What is a savitzky-golay ﬁlter?[lecture notes]. IEEE Signal processing magazine, 28(4):111–117,

2011.

George Tzanetakis, Georg Essl, and Perry Cook. Audio analysis using the discrete wavelet transform. In Proc. Conf. in

Acoustics and Music Theory Applications, volume 66. Citeseer, 2001.

JT Springenberg, A Dosovitskiy, T Brox, and M Riedmiller. Striving for simplicity: The all convolutional net. in arxiv:

cs. arXiv preprint arXiv:1412.6806, 2015.

Linlin Guo, Lei Wang, Chuang Lin, Jialin Liu, Bingxian Lu, Jian Fang, Zhonghao Liu, Zeyang Shan, Jingwen Yang,
and Silu Guo. Wiar: A public dataset for wiﬁ-based activity recognition. IEEE Access, 7:154935–154945, 2019.
Linlin Guo, Hang Zhang, Chao Wang, Weiyu Guo, Guangqiang Diao, Bingxian Lu, Chuang Lin, and Lei Wang.
Towards csi-based diversity activity recognition via lstm-cnn encoder-decoder neural network. Neurocomputing, 444:
260–273, 2021.

14

